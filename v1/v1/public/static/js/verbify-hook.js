/*
  Init modules defined in verbify.js

  requires r.hooks (hooks.js)
 */
!function(r) {
  r.hooks.get('verbify').register(function() {
    try {
        r.setupBackbone();
        r.login.ui.init();
        r.TimeText.init();
        r.ui.init();
        r.interestbar.init();
        r.visited.init();
        r.apps.init();
        r.wiki.init();
        r.sodium.init();
        r.multi.init();
        r.recommend.init();
        r.saved.init();
        r.messages.init();
        r.filter.init();
        r.newsletter.ui.init();
        r.cachePoisoning.init();
        r.locked.init();
    } catch (err) {
        r.sendError('Error during verbify.js init', err.toString());
    }
  });

  $(function() {
    r.hooks.get('verbify').call();
  });
}(r);
