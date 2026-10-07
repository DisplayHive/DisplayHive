// Receives the preview document from the admin (PreviewFrame.vue) and shows it
// in the inner sandboxed frame. Only messages from the embedding admin page are
// accepted.
window.addEventListener('message', function (event) {
  if (event.source !== window.parent) return
  var data = event.data
  if (!data || data.type !== 'dh-preview' || typeof data.html !== 'string') return
  var frame = document.getElementById('dh-preview')
  if (frame) frame.srcdoc = data.html
})
