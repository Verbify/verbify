/*
  Init modules defined in verbify-init.js

  requires r.hooks (hooks.js)
 */
!function(r) {
  r.hooks.get('verbify-init').register(function() {
    try {
        r.events.init();
        r.analytics.init();
        r.access.init();
    } catch (err) {
        r.sendError('Error during verbify-init.js init', err.toString());
    }
  })

  $(function() {
    r.hooks.get('verbify-init').call();
  });
}(r);
