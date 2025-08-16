const steps = [
  { selector: '#portfolioValue', text: 'This shows your portfolio value in SOL and USD.' },
  { selector: '#tradingToggle', text: 'Use Start to begin trading when ready.' },
  { selector: '#strategyPerformance', text: 'Track strategy performance here.' },
];

function startWalkthrough() {
  const overlay = document.getElementById('walkthroughOverlay');
  const textEl = document.getElementById('walkthroughText');
  const nextBtn = document.getElementById('walkthroughNext');
  let index = 0;
  overlay.classList.remove('hidden');
  function showStep(i) {
    const step = steps[i];
    textEl.textContent = step.text;
    document.querySelectorAll('.walk-highlight').forEach(el => el.classList.remove('ring-4','ring-blade-amber','walk-highlight'));
    const el = document.querySelector(step.selector);
    if (el) {
      el.classList.add('ring-4','ring-blade-amber','walk-highlight');
      el.scrollIntoView({behavior:'smooth', block:'center'});
    }
  }
  nextBtn.onclick = () => {
    index += 1;
    if (index >= steps.length) {
      document.querySelectorAll('.walk-highlight').forEach(el => el.classList.remove('ring-4','ring-blade-amber','walk-highlight'));
      overlay.classList.add('hidden');
      localStorage.setItem('basic_walkthrough_pending','false');
      localStorage.setItem('basic_walkthrough_done','true');
    } else {
      showStep(index);
    }
  };
  showStep(index);
}

if (localStorage.getItem('basic_walkthrough_pending') === 'true') {
  window.addEventListener('load', startWalkthrough);
}
