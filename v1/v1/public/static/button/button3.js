(function() {
  var write_string="<iframe src=\"//www.verbifystatic.com/button/button3.html?url=";

  if (window.verbify_url)  { 
      write_string += encodeURIComponent(verbify_url); 
  }
  else { 
      write_string += encodeURIComponent(window.location.href);
  }
  if (window.verbify_title) {
       write_string += '&title=' + encodeURIComponent(window.verbify_title);
  }
  if (window.verbify_target) {
       write_string += '&sr=' + encodeURIComponent(window.verbify_target);
  }
  if (window.verbify_css) {
      write_string += '&css=' + encodeURIComponent(window.verbify_css);
  }
  if (window.verbify_bgcolor) {
      write_string += '&bgcolor=' + encodeURIComponent(window.verbify_bgcolor); 
  }
  if (window.verbify_bordercolor) {
      write_string += '&bordercolor=' + encodeURIComponent(window.verbify_bordercolor); 
  }
  if (window.verbify_newwindow) { 
      write_string += '&newwindow=' + encodeURIComponent(window.verbify_newwindow);}
  write_string += "\" height=\"52\" width=\"69\" scrolling='no' frameborder='0'></iframe>";
  document.write(write_string);
})()
