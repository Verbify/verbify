r.sodium = {

    _inlineSilding: false,

    _googleCheckoutAnalyticsLoaded: false,

    init: function () {
        $('div.content').on(
            'click',
            '[name="message"]',
            this._toggleGiftMessage.bind(this)
        );

        $('div.content').on(
            'click',
            'a.give-sodium, .sodium-payment .close-button',
            this._toggleThingSodiumForm.bind(this)
        );

        // this fires when any of the checkout buttons are clicked
        // updates the signed and giftmessage properties in the payment_blob
        // failures should be rare and it's probably safe for any updates to be lost
        $('div.content').on(
            'click',
            '.sodium-button',
            this._setSildingProperties.bind(this)
        );

        $('.stripe-sodium').click(function(){
            $("#stripe-payment").slideToggle()
        });

        $('#stripe-payment.charge .stripe-submit').on('click', function() {
            r.sodium.tokenThenPost('stripecharge/sodium')
        });

        $('#stripe-payment.modify .stripe-submit').on('click', function() {
            r.sodium.tokenThenPost('modify_subscription')
        });

        $('h3.toggle').on('click', function() {
          $(this).toggleClass('toggled');
          $(this).siblings('.details').slideToggle();
        });

        $('dt.toggle').on('click', function() {
          $(this).toggleClass('toggled');
          $(this).next('dd').slideToggle();
        });

        if ($('body').hasClass('sodium-signup')) {
          r.sodium.signupForm.init();
        }

        $('form.cverbifys-sodium .remaining').each(r.sodium._renderCverbifysAmount);

        $(document.body).on('submit', 'form.cverbifys-sodium', function(e) {
          e.preventDefault();
          e.stopPropagation();

          r.sodium._expendCverbifys();

          $(this).find('.sodium-checkout:not(.cverbifys-sodium)').hide();
          return post_form(this, 'spendcverbifys')
        })
    },

    _toggleGiftMessage: function(e){
        var messageCheckbox = e.target;
        var includeMsg = messageCheckbox.checked;
        var giftmessage_id = $(e.target).parents('.sodium-form').find('[name="giftmessage"]').attr('id');
        var $form = $('#' + giftmessage_id);

        $form.toggleClass('hidden', !includeMsg);
    },
    
    _toggleThingSodiumForm: function (e) {
        if (r.access.isLinkRestricted(e.target)) {
          return;
        }

        var $link = $(e.target);
        var $thing = $link.thing();
        var thingFullname = $link.thing_id();
        var wrapId = 'sodium_wrap_' + thingFullname;
        var oldWrap = $('#' + wrapId);
        var cloneClass;

        if (oldWrap.length) {
            oldWrap.toggle();
            return false
        }

        this._inlineSilding = true;

        r.analytics.fireFunnelEvent('sodium', 'open-inline-form', {
          tracker: 'sodiumTracker'
        });

        if (!this._googleCheckoutAnalyticsLoaded) {
            // we're just gonna hope this loads fast enough since there's no
            // way to know if it failed and we'd rather the form is still
            // usable if things don't go well with the analytics stuff.
            $.getScript('//checkout.google.com/files/digital/ga_post.js');
            this._googleCheckoutAnalyticsLoaded = true
        }

        if ($thing.hasClass('link')) {
            cloneClass = 'cloneable-link'
        } else {
            cloneClass = 'cloneable-comment'
        }

        var sodiumwrap = $('.sodium-wrap.' + cloneClass + ':first').clone();
        var form = sodiumwrap.find('.sodium-form');
        var authorName = $link.thing().find('.entry .author:first').text();
        var passthroughs = form.find('.passthrough');
        var cbBaseUrl = form.find('[name="cbbaseurl"]').val();
        var signed = !(form.find('[name="signed"]')).is(':checked');

        sodiumwrap
          .removeClass(cloneClass)
          .addClass('inline-sodium')
          .prop('id', wrapId);

        form.find('p:first-child em').text(authorName);
        form.find('button').attr('disabled', '');
        passthroughs.val('');

        $link.new_thing_child(sodiumwrap);

        // show the throbber if this takes longer than 200ms
        var workingTimer = setTimeout(function () {
            form.addClass('working');
            form.find('button').addClass('disabled')
        }, 200);

        $.request('generate_payment_blob.json', {thing: thingFullname, signed: signed}, function (token) {
            clearTimeout(workingTimer);
            form.removeClass('working');
            passthroughs.val(token);
            form.find('.stripe-sodium').on('click', function() { window.open('/sodium/creditsild/' + token) });
            form.find('.coinbase-sodium').on('click', function() { window.open(cbBaseUrl + "?c=" + token) });
            form.find('button').removeAttr('disabled').removeClass('disabled')
        });

        return false
    },

    _setSildingProperties: function (e) {
        var $button = $(e.target);
        var thingFullname = $button.thing_id();

        // If /sodium, then don't set signed and message properties
        if (!thingFullname) {
          $button.parents('form').submit();
          return;
        }

        var wrapId = 'sodium_wrap_' + thingFullname;
        var $sodiumwrap = $('#' + wrapId);
        var passthroughs = $sodiumwrap.find('.passthrough');
        var code = passthroughs.val();
        var signed = !$sodiumwrap.find('[name="signed"]').is(':checked');
        var includeMsg = $sodiumwrap.find('[name="message"]').is(':checked');
        var giftmessage = "";

        if (includeMsg) {
          giftmessage = ($sodiumwrap.find('[name="giftmessage"]')).val();
        }

        if (this._inlineSilding) {
          var options = {
            label: $button.closest('[data-vendor]').data('vendor'),
            tracker: 'sodiumTracker'
          };
          r.analytics.fireFunnelEvent('sodium', 'checkout', options);
        }

        $.request('modify_payment_blob.json', {code: code, signed: signed, message: giftmessage}, function() {
          $button.parents('form').submit();
        });
    },

    // When spending cverbifys, update the templates we use to generate the silding form to display the
    // new total cverbifys remaining, or hide it if we have less than the current cost of silding (1 cverbify).
    _expendCverbifys: function() {
      $('.cloneable-comment, .cloneable-link').find('form.cverbifys-sodium .remaining').each(function() {
        var $this = $(this);
        var currentCverbifys = parseInt($this.data('current'), 10);
        var totalCverbifys = parseInt($this.data('total'), 10);
        var newTotal = totalCverbifys - currentCverbifys;

        if (newTotal < currentCverbifys) {
          $this.parents('form.cverbifys-sodium').remove()
        } else {
          $(this).data('total', newTotal);
          r.sodium._renderCverbifysAmount.apply(this)
        }
      })
    },

    _renderCverbifysAmount: function() {
      var $this = $(this);
      var tpl = $this.data('template');
      $this.html(_.template(tpl, _.omit($this.data(), 'template')))
    },

    sildThing: function (thing_fullname, new_title, specified_silding_count) {
        var thing = $('.id-' + thing_fullname);

        if (!thing.length) {
            console.log("couldn't sild thing " + thing_fullname);
            return
        }

        var tagline = thing.children('.entry').find('p.tagline'),
            icon = tagline.find('.silded-icon');

        // when a thing is silded interactively, we need to increment the
        // silding count displayed by the UI. however, when sildings are
        // instantiated from a cached comment page via thingupdater, we can't
        // simply increment the silding count because we do not know if the
        // cached comment page already includes the silding in its count. To
        // resolve this ambiguity, thingupdater will provide the correct
        // silding count as specified_silding_count when calling this function.
        var silding_count;
        if (specified_silding_count != null) {
            silding_count = specified_silding_count
        } else {
            silding_count = icon.data('count') || 0;
            silding_count++
        }

        thing.addClass('silded user-silded');
        if (!icon.length) {
            icon = $('<span>')
                        .addClass('silded-icon');
            tagline.append(icon)
        }
        icon
            .attr('title', new_title)
            .data('count', silding_count);
        if (silding_count > 1) {
            icon.text('x' + silding_count)
        }

        thing.children('.entry').find('.give-sodium').parent().remove()
    },

    tokenThenPost: function (dest) {
        var postOnSuccess = function (status_code, response) {
            var form = $('#stripe-payment'),
                submit = form.find('.stripe-submit'),
                status = form.find('.status'),
                token = form.find('[name="stripeToken"]');

            if (response.error) {
                submit.removeAttr('disabled');
                status.html(response.error.message)
            } else {
                token.val(response.id);
                post_form(form, dest)
            }
        };
        r.sodium.makeStripeToken(postOnSuccess)
    },

    makeStripeToken: function (responseHandler) {
        var form = $('#stripe-payment'),
            publicKey = form.find('[name="stripePublicKey"]').val(),
            submit = form.find('.stripe-submit'),
            status = form.find('.status'),
            token = form.find('[name="stripeToken"]'),
            cardName = form.find('.card-name').val(),
            cardNumber = form.find('.card-number').val(),
            cardCvc = form.find('.card-cvc').val(),
            expiryMonth = form.find('.card-expiry-month').val(),
            expiryYear = form.find('.card-expiry-year').val(),
            cardAddress1 = form.find('.card-address_line1').val(),
            cardAddress2 = form.find('.card-address_line2').val(),
            cardCity = form.find('.card-address_city').val(),
            cardState = form.find('.card-address_state').val(),
            cardCountry = form.find('.card-address_country').val(),
            cardZip = form.find('.card-address_zip').val();
        Stripe.setPublishableKey(publicKey);

        var showError = function(inputSelector, str) {
          form.find('.status')
            .addClass('error')
            .text(str);
          $(inputSelector).focus()
        };

        if (!cardName) {
            showError('.card-name', r._('missing name'))
        } else if (!(Stripe.validateCardNumber(cardNumber))) {
            showError('.card-number', r._('invalid credit card number'))
        } else if (!Stripe.validateExpiry(expiryMonth, expiryYear)) {
            showError('.card-expiry-month', r._('invalid expiration date'))
        } else if (!Stripe.validateCVC(cardCvc)) {
            showError('.card-cvc', r._('invalid cvc'))
        } else if (!cardAddress1) {
            showError('.card-address_line1', r._('missing address'))
        } else if (!cardCity) {
            showError('.card-address_city', r._('missing city'))
        } else if (!cardCountry) {
            showError('.card-address_country', r._('missing country'))
        } else {
            status
              .removeClass('error')
              .text(r.config.status_msg.submitting);
            submit.attr('disabled', 'disabled');
            Stripe.createToken({
                    name: cardName,
                    number: cardNumber,
                    cvc: cardCvc,
                    exp_month: expiryMonth,
                    exp_year: expiryYear,
                    address_line1: cardAddress1,
                    address_line2: cardAddress2,
                    address_city: cardCity,
                    address_state: cardState,
                    address_country: cardCountry,
                    address_zip: cardZip
                }, responseHandler
            )
        }
        return false
    }
};

r.sodium.signupForm = (function() {

  // Get all field names relevant to this sodiumtype.
  // This helps us keep a clean URL state.
  function _getRelevantFields() {
    var sodiumtype = $('#sodiumtype').val();
    var fields = ['sodiumtype'];

    switch (sodiumtype) {
      case 'autorenew':
        fields.push('period');
        break;
      case 'onetime':
        fields.push('months');
        break;
      case 'code':
        fields.push('months', 'email');
        break;
      case 'gift':
        fields.push('months', 'recipient', 'signed', 'giftmessage');
        break;
      case 'cverbifys':
        fields.push('num_cverbifys');
        break
    }

    return fields
  }

  // Given a field, get its value, regardless of input type.
  function _getFieldValue(field) {
    var $field = $(field);

    if ($field.is(':radio') && !$field.is(':checked')) {
      throw 'Unchecked radio button has no value'
    }

    if ($field.is(':checkbox')) {
      value = $field.is(':checked') ? $field.val() : null
    } else if ($field.is('select')) {
      value = $field.find('option:selected').val()
    } else {
      value = $field.val()
    }

    return value
  }

  function _updateUrlState() {
    var a = $("<a />").get(0);
    var urlFields = _getRelevantFields();
    var params = {};

    if (!('replaceState' in window.history)) {
      return
    }

    $('form.sodium-form').find(':input').each(function() {
      var $field = $(this)

      if (!_.contains(urlFields, this.name)) {
        return
      }

      try {
        params[this.name] = _getFieldValue(this)
      } catch(e) {
        return
      }
    });

    params['edit'] = true;

    a.href = window.location.href;
    a.search = $.param(params);
    window.history.replaceState({}, "", a.href)
  }

  function _updateSodiumType() {
    var $gifttype = $('input[name="gifttype"]:checked');
    var $tab = $('.tab.active');
    var isGift = $('#gift').is(':checked');
    var sodiumtype;

    if ($tab.prop('id') == 'autorenew') {
      sodiumtype = 'autorenew'
    } else if ($tab.prop('id') == 'cverbifys') {
      sodiumtype = 'cverbifys'
    } else if (isGift && $gifttype.length > 0) {
      sodiumtype = $gifttype.val()
    } else {
      sodiumtype = 'onetime'
    }

    $('#sodiumtype').val(sodiumtype);
    _updateUrlState()
  }

  function _setTabFocus(tab) {
    $('#form-options, #payment-options').show();

    $('.active').removeClass('active');
    $('#redeem-a-code, .question').hide();

    $(tab).addClass('active');
    $(tab.hash).addClass('active');

    _updateSodiumType()
  }

  // On submit, pass only the relevant fields to the payment page, for clean URLs and proper
  // display of the payment summary.
  function _handleSubmit(e) {
    e.stopPropagation();
    e.preventDefault();

    /* Our IE placeholder handling is miserable, clear out placeholder text before submission if we have it. */
    $('#giftmessage, #recipient').each(function() {
      var $this = $(this);
      if ($this.val() === $this.attr('placeholder')) {
        $this.val('')
      }
    });

    // serializeArray returns an array of objects, turn it into key/value pairs
    // since we're not worried about multi-value keys and it's what $.param expects
    var fields = $('form.sodium-form').serializeArray();
    var fieldsAsDict = _.object(_.pluck(fields, 'name'), _.pluck(fields, 'value'));

    // Only submit fields that are relevant to this sodiumtype
    var submission = _.pick(fieldsAsDict, _getRelevantFields());

    window.location = "/sodium/payment?" + $.param(submission)
  }

  function init() {
    var $form = $('form.sodium-form');

    $('a.tab-toggle').on('click', function(e) {
      e.stopPropagation();
      e.preventDefault();

      _setTabFocus(this)
    });

    $('input[name="gift"]').change(function() {
      $('#gifting-details').slideToggle($(this).val());
      _updateSodiumType()
    });

    // Workaround for our form cloning to maintain back buttons. When we clone the form
    // the selected attribute is respected more than the current state unless we explicitly alter it
    $('.sodium-dropdown').on('change', function() {
      $(this).find('[selected]').removeAttr('selected');
      $(this).find(':selected').get(0).setAttribute('selected', 'selected')
    });

    var hasPlaceholder = ('placeholder' in document.createElement('input'));
    $('input[name="gifttype"]').change(function() {
      $('#gifttype-details-gift').toggleClass('hidden', this.value !== 'gift');
      if (hasPlaceholder) {
        $('#gifttype-details-gift :input:eq(0)').focus()
      }
      _updateSodiumType()
    });

    $('#giftmessage').on('keyup', function() {
      $('#message').prop('checked', $(this).val() !== '')
    });

    $form.on('submit', _handleSubmit);

    $form.find(':input').on('change', _updateUrlState);

    $('input[name="code"]').on('focus', function() {
      $('.redeem-submit').slideDown()
    })
  }

  return {
    'init': init
  }
}());

!(function($) {
    $.sild_thing = function (thing_fullname, new_title) {
        r.sodium.sildThing(thing_fullname, new_title);
        $('#sodium_wrap_' + thing_fullname).fadeOut(400)
    }
})(jQuery);
