if('serviceWorker' in navigator){
  window.addEventListener('load',()=>{
    navigator.serviceWorker.register('/static/sw.js').catch(()=>{})
  })
}
setTimeout(()=>document.querySelectorAll('.alert').forEach(el=>{el.style.transition='opacity .4s';el.style.opacity='0';setTimeout(()=>el.remove(),400)}),4000)
