// Animate the actual heading into place, rather than swapping two logos.
(() => {
  const card = document.querySelector('.login-card');
  const brand = document.getElementById('loginBrand');
  const overlay = document.querySelector('.login-arrival');
  const form = document.getElementById('loginForm');
  const subtitle = document.querySelector('.login-subtitle');
  if (!card || !brand || !brand.animate || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const animations = [];
  let finished = false;
  function finish() {
    if (finished) return;
    finished = true;
    card.classList.remove('login-intro-active');
    form.inert = false;
    brand.style.visibility = '';
    animations.forEach(a => a.cancel());
    clearTimeout(fallback);
    window.removeEventListener('resize', finish);
  }
  brand.style.visibility = 'hidden';
  card.classList.add('login-intro-active');
  form.inert = true;
  const fallback = setTimeout(finish, 2600);
  window.addEventListener('resize', finish, {once:true});
  // Short font wait keeps the target stable without delaying sign-in on slow networks.
  Promise.race([document.fonts?.ready || Promise.resolve(), new Promise(resolve => setTimeout(resolve,150))]).then(() => {
    if (finished) return;
    const box = brand.getBoundingClientRect();
    const scale = Math.min(1.55, (innerWidth-48)/box.width);
    const initial = `translate(${innerWidth/2-box.left-box.width/2}px, ${innerHeight/2-box.top-box.height/2}px) scale(${scale})`;
    brand.style.visibility = '';
    animations.push(brand.animate([
      {transform:initial,color:'#f5f9fc',textShadow:'0 0 0px #d5eaff00',offset:0},
      {transform:initial,color:'#f5f9fc',textShadow:'0 0 18px #d5eaff99, 0 0 45px #b6d7ee44',offset:.34},
      {transform:initial,color:'#f5f9fc',textShadow:'0 0 12px #d5eaff66',offset:.44},
      {transform:'translate(0,0) scale(1)',color:'#102536',textShadow:'0 0 0px #d5eaff00',offset:1}
    ],{duration:1550,easing:'cubic-bezier(.4,0,.2,1)',fill:'both'}));
    animations.push(overlay.animate([{opacity:1},{opacity:0}],{delay:850,duration:700,fill:'both',easing:'ease-in-out'}));
    for (const el of [form,subtitle]) animations.push(el.animate([
      {opacity:0,transform:'translateY(10px)'},{opacity:1,transform:'translateY(0)'}
    ],{delay:1150,duration:500,fill:'both',easing:'ease-out'}));
    Promise.all(animations.map(a => a.finished)).then(finish,finish);
  }).catch(finish);
})();
