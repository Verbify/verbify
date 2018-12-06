r.traffic = {
    init: function () {
        // add a simple method of jumping to any subverbify's traffic page
        if ($('body').hasClass('traffic-sitewide'))
            this.addSubverbifySelector()
    },

    addSubverbifySelector: function () {
        $('<form>').append(
            $('<fieldset>').append(
                $('<legend>').text(r._('view subverbify traffic')),
                $('<input type="text" id="srname">'),
                $('<input type="submit">').attr('value', r._('go'))
            )
        ).submit(r.traffic._onSubverbifySelected)
        .prependTo('.traffic-tables-side')
    },

    _onSubverbifySelected: function () {
        var srname = $(this.srname).val()

        window.location = window.location.protocol + '//' +
                          r.config.cur_domain +
                          '/r/' + srname +
                          '/about/traffic'

        return false
    }
}

$(function () {
    r.traffic.init()
})
