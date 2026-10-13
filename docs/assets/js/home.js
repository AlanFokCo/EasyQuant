/* EasyQuant landing interactions — homepage only (html.eq-landing) */
(function () {
  'use strict';
  if (!document.documentElement.classList.contains('eq-landing')) return;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ================= Hero chart: TradingView Lightweight Charts =================
     Professional candlestick chart (A-share convention: red=up, green=down)
     with a MA-cross strategy equity overlay. Deterministic synthetic data.
     Falls back to a hand-drawn canvas when the library is unavailable. */
  var heroEl = document.querySelector('.eql-hero');
  var chartBox = heroEl && heroEl.querySelector('.eql-chart');
  var canvas = heroEl && heroEl.querySelector('canvas');

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function genSeries() {
    var rnd = mulberry32(20261013);
    var days = [], d = new Date(2025, 3, 1);
    while (days.length < 150) {
      if (d.getDay() !== 0 && d.getDay() !== 6) {
        days.push(d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'));
      }
      d.setDate(d.getDate() + 1);
    }
    var candles = [], equity = [];
    var price = 18.5, eq = 100, holding = false, entry = 0;
    for (var i = 0; i < days.length; i++) {
      var regime = Math.sin(i * 0.055) * 0.0016 + (i > 95 ? 0.0012 : 0);   // slow trend regimes
      var vol = 0.014 + 0.012 * Math.abs(Math.sin(i * 0.021));            // vol clustering
      var ret = regime + (rnd() - 0.5) * 2 * vol;
      var open = price * (1 + (rnd() - 0.5) * vol * 0.5);
      var close = open * (1 + ret);
      var high = Math.max(open, close) * (1 + rnd() * vol * 0.65);
      var low = Math.min(open, close) * (1 - rnd() * vol * 0.65);
      candles.push({ time: days[i], open: round2(open), high: round2(high), low: round2(low), close: round2(close) });
      // MA-cross strategy equity (thematic overlay)
      if (i >= 20) {
        var ma = 0;
        for (var j = i - 20; j < i; j++) ma += candles[j].close;
        ma /= 20;
        if (!holding && close > ma * 1.02) { holding = true; entry = close; }
        else if (holding && close < ma * 0.98) { eq *= (close / entry); holding = false; }
      }
      if (holding) equity.push({ time: days[i], value: eq * (close / entry) });
      else equity.push({ time: days[i], value: eq });
      price = close;
    }
    function round2(v) { return Math.round(v * 100) / 100; }
    // light EMA smoothing so the overlay reads as an equity curve, not noise
    var alpha = 0.35, sm = [];
    for (var k = 0; k < equity.length; k++) {
      var prev = k ? sm[k - 1] : equity[0].value;
      sm.push({ time: equity[k].time, value: prev + alpha * (equity[k].value - prev) });
    }
    return { candles: candles, equity: sm };
  }

  var lwActive = false;
  if (chartBox && window.LightweightCharts) {
    lwActive = true;
    chartBox.classList.add('is-live');
    var chart = LightweightCharts.createChart(chartBox, {
      layout: {
        background: { type: 'solid', color: 'transparent' },
        textColor: 'rgba(151,163,171,0.55)',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 10,
        attributionLogo: false
      },
      grid: {
        vertLines: { color: 'rgba(237,242,243,0.045)' },
        horzLines: { color: 'rgba(237,242,243,0.045)' }
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
      crosshair: {
        vertLine: { color: 'rgba(201,164,92,0.45)', width: 1, style: 3, labelBackgroundColor: '#c9a45c' },
        horzLine: { color: 'rgba(201,164,92,0.45)', width: 1, style: 3, labelBackgroundColor: '#c9a45c' }
      }
    });
    var cs = chart.addCandlestickSeries({
      upColor: '#e63946', downColor: 'rgba(23,169,116,0.85)',
      wickUpColor: 'rgba(230,57,70,0.85)', wickDownColor: 'rgba(23,169,116,0.7)',
      borderVisible: false,
      priceLineVisible: false
    });
    var eqs = chart.addLineSeries({
      color: '#c9a45c', lineWidth: 2, priceScaleId: 'left',
      crosshairMarkerVisible: false, priceLineVisible: false, lastValueVisible: false
    });
    chart.priceScale('left').applyOptions({ visible: false });
    var data = genSeries();
    cs.setData(data.candles);
    eqs.setData(data.equity);
    chart.timeScale().fitContent();
    var rto;
    window.addEventListener('resize', function () {
      clearTimeout(rto);
      rto = setTimeout(function () {
        var r = heroEl.getBoundingClientRect();
        chart.resize(Math.floor(r.width), Math.floor(r.height));
      }, 120);
    });
  }

  /* ---------- Fallback: hand-drawn canvas hero ---------- */
  if (!lwActive && canvas && !reduced) {
    var ctx = canvas.getContext('2d');
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var W = 0, H = 0, fCandles = [], fLine = [], start = 0, raf = 0, running = true;
    var UP = '230,57,70', DOWN = '23,169,116';

    function seed() {
      fCandles = []; fLine = [];
      var price = 100, n = Math.max(28, Math.floor(W / 34));
      var rnd = mulberry32(20261013);
      for (var i = 0; i < n; i++) {
        var drift = Math.sin(i * 0.24) * 1.6 + (rnd() - 0.46) * 4.4;
        var o = price, c = o + drift;
        var hi = Math.max(o, c) + rnd() * 2.4;
        var lo = Math.min(o, c) - rnd() * 2.4;
        fCandles.push({ o: o, c: c, hi: hi, lo: lo });
        fLine.push(c);
        price = c;
      }
      var min = Infinity, max = -Infinity;
      fCandles.forEach(function (k) { min = Math.min(min, k.lo); max = Math.max(max, k.hi); });
      var pad = (max - min) * 0.18 + 1;
      fCandles.forEach(function (k) {
        k.yO = norm(k.o, min - pad, max + pad); k.yC = norm(k.c, min - pad, max + pad);
        k.yH = norm(k.hi, min - pad, max + pad); k.yL = norm(k.lo, min - pad, max + pad);
      });
      fLine = fLine.map(function (v) { return norm(v, min - pad, max + pad); });
    }
    function norm(v, lo, hi) { return H * 0.86 - ((v - lo) / (hi - lo)) * H * 0.68; }

    function draw(t) {
      if (!running) return;
      if (!start) start = t;
      var p = Math.min((t - start) / 2200, 1);
      var ease = 1 - Math.pow(1 - p, 3);
      ctx.clearRect(0, 0, W, H);
      ctx.strokeStyle = 'rgba(237,242,243,0.045)';
      ctx.lineWidth = 1;
      for (var gy = H * 0.18; gy < H * 0.9; gy += H * 0.12) {
        ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke();
      }
      var n = fCandles.length, cw = W / n, shown = Math.floor(ease * n);
      for (var i = 0; i < shown; i++) {
        var k = fCandles[i], x = i * cw + cw * 0.5;
        var up = k.c >= k.o, col = up ? UP : DOWN;
        ctx.strokeStyle = 'rgba(' + col + ',0.55)';
        ctx.beginPath(); ctx.moveTo(x, k.yH); ctx.lineTo(x, k.yL); ctx.stroke();
        ctx.fillStyle = up ? 'rgba(' + UP + ',0.85)' : 'rgba(' + DOWN + ',0.55)';
        var top = Math.min(k.yO, k.yC), h = Math.max(Math.abs(k.yC - k.yO), 1.5);
        ctx.fillRect(x - cw * 0.26, top, cw * 0.52, h);
      }
      if (shown > 1) {
        ctx.save();
        ctx.strokeStyle = 'rgba(201,164,92,0.9)'; ctx.lineWidth = 1.6;
        ctx.shadowColor = 'rgba(201,164,92,0.5)'; ctx.shadowBlur = 10;
        ctx.beginPath();
        for (var j = 0; j < shown; j++) {
          var lx = j * cw + cw * 0.5;
          if (j === 0) ctx.moveTo(lx, fLine[0]); else ctx.lineTo(lx, fLine[j]);
        }
        ctx.stroke(); ctx.restore();
        var ex = (shown - 1) * cw + cw * 0.5, ey = fLine[shown - 1];
        var pulse = 2.4 + Math.sin(t / 300) * 1.1;
        ctx.fillStyle = 'rgba(201,164,92,0.95)';
        ctx.beginPath(); ctx.arc(ex, ey, pulse, 0, Math.PI * 2); ctx.fill();
      }
      raf = requestAnimationFrame(draw);
    }
    function resize() {
      var r = canvas.parentElement.getBoundingClientRect();
      W = Math.floor(r.width); H = Math.floor(r.height);
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
    }
    resize();
    window.addEventListener('resize', resize);
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        var was = running; running = e.isIntersecting;
        if (running && !was) { start = performance.now() - 1800; raf = requestAnimationFrame(draw); }
        if (!running) cancelAnimationFrame(raf);
      });
    });
    io.observe(canvas);
    raf = requestAnimationFrame(draw);
  }

  /* ---------- Count-up stats ---------- */
  var nums = document.querySelectorAll('[data-eql-count]');
  if (nums.length && 'IntersectionObserver' in window) {
    var cio = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        cio.unobserve(e.target);
        var el = e.target, target = parseFloat(el.getAttribute('data-eql-count'));
        var dec = (el.getAttribute('data-eql-count').split('.')[1] || '').length;
        if (reduced) { el.firstChild.nodeValue = target.toFixed(dec); return; }
        var t0 = performance.now(), dur = 1500;
        (function tick(t) {
          var p = Math.min((t - t0) / dur, 1);
          var v = target * (1 - Math.pow(1 - p, 4));
          el.firstChild.nodeValue = v.toFixed(dec).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
          if (p < 1) requestAnimationFrame(tick);
        })(t0);
      });
    }, { threshold: 0.4 });
    nums.forEach(function (el) { cio.observe(el); });
  }

  /* ---------- Scroll reveals ---------- */
  var revs = document.querySelectorAll('.eql-reveal');
  if (revs.length && 'IntersectionObserver' in window && !reduced) {
    var rio = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('is-in'); rio.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -4% 0px' });
    revs.forEach(function (el) {
      el.style.transitionDelay = (el.getAttribute('data-eql-delay') || 0) + 'ms';
      rio.observe(el);
    });
  } else {
    revs.forEach(function (el) { el.classList.add('is-in'); });
  }

  /* ---------- Install copy button ---------- */
  document.querySelectorAll('.eql-install__copy').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var cmd = btn.parentElement.querySelector('.cmd').textContent;
      var done = function () {
        var old = btn.textContent;
        btn.textContent = btn.getAttribute('data-copied') || 'copied';
        setTimeout(function () { btn.textContent = old; }, 1600);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(cmd).then(done, done);
      else done();
    });
  });

  /* ---------- Terminal typing ---------- */
  var term = document.querySelector('.eql-term__body[data-eql-type]');
  if (term) {
    if (reduced) { colorize(term); }
    else {
      var started = false;
      var tio = new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting && !started) { started = true; tio.disconnect(); typewriter(); }
        });
      }, { threshold: 0.3 });
      tio.observe(term);
      function typewriter() {
        var plain = term.textContent, i = 0;
        term.textContent = '';
        var caret = document.createElement('span'); caret.className = 'eql-caret';
        term.appendChild(caret);
        (function step() {
          if (i < plain.length) {
            term.insertBefore(document.createTextNode(plain.charAt(i)), caret);
            var ch = plain.charAt(i); i++;
            setTimeout(step, ch === '\n' ? 60 : (14 + Math.random() * 26));
          } else { caret.remove(); colorize(term); }
        })();
      }
    }
    function colorize(el) {
      var txt = el.textContent;
      el.innerHTML = txt
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/(#.*$)/gm, '<span class="c">$1</span>')
        .replace(/'([^']*)'/g, '<span class="s">\'$1\'</span>')
        .replace(/\b(from|import|def|if|elif|return|and|or|not|in|for|while)\b/g, '<span class="k">$1</span>')
        .replace(/\b(run_strategy|run_daily|set_benchmark|attribute_history|order_value|order_target|initialize|market_open|print)\b/g, '<span class="f">$1</span>')
        .replace(/(✓.*$)/gm, '<span class="ok">$1</span>')
        .replace(/(\+\d+\.\d+%)/g, '<span class="hl">$1</span>');
    }
  }

  /* ---------- Ticker: duplicate content for seamless marquee ---------- */
  var track = document.querySelector('.eql-ticker__track');
  if (track && !track.getAttribute('data-eql-duped')) {
    track.innerHTML += track.innerHTML;
    track.setAttribute('data-eql-duped', '1');
  }
})();
