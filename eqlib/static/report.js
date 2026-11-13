/* ============================================================================
   EasyQuant Backtest Report — chart engine
   Hand-rolled SVG. Zero dependencies. All values come from the embedded
   JSON payload computed by Python; this layer does geometry only.
   ========================================================================== */
(function () {
  'use strict';

  var payloadEl = document.getElementById('eq-report-data');
  if (!payloadEl) return;
  var DATA;
  try { DATA = JSON.parse(payloadEl.textContent); } catch (e) { return; }

  var NS = 'http://www.w3.org/2000/svg';
  var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Colors (kept in sync with report.css) */
  var C = {
    accent: '#2962ff', accentHover: '#3b74ff',
    up: '#26a69a', down: '#ef5350',
    bench: '#d95926', warn: '#e0a32e',
    ma5: '#6da7ec', ma20: '#3987e5', ma60: '#1c5cab',
    gridline: '#252a37', axisLine: '#2e3344', crosshair: '#59617a',
    ink3: '#6a7183', ink4: '#4c5265', neutral: '#3a3f52',
    surface: '#1e222d'
  };

  /* ------------------------------------------------------------------ */
  /* Small DOM/SVG helpers                                               */
  /* ------------------------------------------------------------------ */
  function el(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function div(cls, parent, text) {
    var n = document.createElement('div');
    if (cls) n.className = cls;
    if (parent) parent.appendChild(n);
    if (text != null) n.textContent = text;
    return n;
  }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  /* Index-based x axis: trading days are categorical positions. */
  function xScale(i0, i1, w) {
    var span = Math.max(1, i1 - i0);
    return {
      x: function (i) { return (i - i0) / span * w; },
      inv: function (px) { return clamp(Math.round(px / w * span + i0), i0, i1); },
      step: w / span
    };
  }
  function yScale(v0, v1, h, padTop) {
    if (v0 === v1) { v0 -= 1; v1 += 1; }
    var pad = (v1 - v0) * 0.06;
    v0 -= pad; v1 += pad;
    var top = padTop || 0;
    return {
      y: function (v) { return top + (1 - (v - v0) / (v1 - v0)) * (h - top); },
      inv: function (py) { return v0 + (1 - (py - top) / (h - top)) * (v1 - v0); },
      min: v0, max: v1
    };
  }

  /* Nice tick marks — choose the 0.5/1/2/2.5/5/10 step whose tick count is
     closest to the target, with a hard floor of 2 ticks. */
  function niceTicks(v0, v1, target) {
    var span = v1 - v0;
    if (!isFinite(span) || span <= 0) return [v0];
    target = Math.max(2, target || 4);
    var mag = Math.pow(10, Math.floor(Math.log10(span / target)));
    var bestStep = 0, bestScore = Infinity;
    [0.5, 1, 2, 2.5, 5, 10, 20, 50].forEach(function (m) {
      var step = m * mag;
      var count = Math.floor(v1 / step + 1e-9) - Math.ceil(v0 / step - 1e-9) + 1;
      if (count < 2) return;
      var score = Math.abs(count - target) - (count >= target ? 0.2 : 0);
      if (score < bestScore) { bestScore = score; bestStep = step; }
    });
    if (!bestStep) bestStep = mag;
    var out = [];
    for (var t = Math.ceil(v0 / bestStep) * bestStep; t <= v1 + 1e-12; t += bestStep) out.push(+t.toFixed(10));
    return out.length >= 2 ? out : [v0, v1];
  }

  /* Bar path: 4px rounded data-end, square at the baseline (mark spec). */
  function barRectPath(x, y, w, h, up) {
    var r = Math.min(4, w / 2, Math.abs(h));
    if (r < 0.5) return 'M' + x + ' ' + y + 'h' + w + ' ' + 'V' + (y + h) + 'H' + x + 'Z';
    if (up) {
      return 'M' + x + ' ' + (y + h) + 'L' + x + ' ' + (y + r) +
        'Q' + x + ' ' + y + ' ' + (x + r) + ' ' + y +
        'L' + (x + w - r) + ' ' + y +
        'Q' + (x + w) + ' ' + y + ' ' + (x + w) + ' ' + (y + r) +
        'L' + (x + w) + ' ' + (y + h) + 'Z';
    }
    return 'M' + x + ' ' + y + 'L' + (x + w) + ' ' + y +
      'L' + (x + w) + ' ' + (y + h - r) +
      'Q' + (x + w) + ' ' + (y + h) + ' ' + (x + w - r) + ' ' + (y + h) +
      'L' + (x + r) + ' ' + (y + h) +
      'Q' + x + ' ' + (y + h) + ' ' + x + ' ' + (y + h - r) + 'Z';
  }

  /* Date axis ticks: year boundaries when spanning > ~700 bars, else quarters/months */
  function dateTicks(dates, i0, i1, maxTicks) {
    var out = [], lastLabel = '';
    var spanBars = i1 - i0;
    var stride = Math.max(1, Math.round(spanBars / Math.max(2, maxTicks)));
    function labelFor(i) {
      var d = dates[i]; if (!d) return '';
      var y = d.slice(0, 4), m = d.slice(5, 7);
      if (spanBars > 600) return m === '01' || !lastLabel ? y : y;
      if (spanBars > 160) return y + '-' + m;
      return m + '-' + d.slice(8, 10);
    }
    for (var i = i0; i <= i1; i += stride) {
      var lab = labelFor(i);
      if (lab && lab !== lastLabel) { out.push({ i: i, label: lab }); lastLabel = lab; }
    }
    if (out.length && out[0].i === i0 && i0 > 0) { /* keep */ }
    return out;
  }

  /* ------------------------------------------------------------------ */
  /* Formatters — display only, values originate in Python               */
  /* ------------------------------------------------------------------ */
  function fmtPct(v, dp) { return isNum(v) ? v.toFixed(dp == null ? 2 : dp) + '%' : '—'; }
  function fmtSignedPct(v, dp) { return isNum(v) ? (v >= 0 ? '+' : '') + v.toFixed(dp == null ? 2 : dp) + '%' : '—'; }
  function fmtPctFrac(v, dp) { return isNum(v) ? (v * 100).toFixed(dp == null ? 2 : dp) + '%' : '—'; }
  function fmtNum(v, dp) { return isNum(v) ? v.toFixed(dp == null ? 2 : dp) : '—'; }
  function fmtInt(v) { return isNum(v) ? Math.round(v).toLocaleString('zh-CN') : '—'; }
  function fmtMoney(v) {
    if (!isNum(v)) return '—';
    var sign = v < 0 ? '-' : '';
    var a = Math.abs(v);
    if (a >= 1e8) return sign + (a / 1e8).toFixed(2) + ' 亿';
    if (a >= 1e4) return sign + (a / 1e4).toFixed(2) + ' 万';
    return sign + a.toLocaleString('zh-CN', { maximumFractionDigits: 0 });
  }
  function fmtVol(v) {
    if (!isNum(v)) return '—';
    if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿';
    if (v >= 1e4) return (v / 1e4).toFixed(1) + ' 万';
    return Math.round(v).toLocaleString('zh-CN');
  }
  function clsDelta(v) { return !isNum(v) ? '' : v >= 0 ? 'up' : 'down'; }

  /* Date axis with edge-clamped labels (shared by every chart) */
  function drawDateAxis(g, dates, i0, i1, xs, y, plotW) {
    var ticks = dateTicks(dates, i0, i1, Math.max(3, Math.floor(plotW / 110)));
    ticks.forEach(function (tk) {
      var x = xs.x(tk.i);
      var anchor = 'middle';
      if (x < 30) anchor = 'start';
      else if (x > plotW - 30) anchor = 'end';
      var t = el('text', { 'class': 'axis-text', x: x, y: y, 'text-anchor': anchor }, g);
      t.textContent = tk.label;
    });
  }

  /* Halo for text over data (legibility without wearing the data color) */
  function haloText(attrs, text, g) {
    var t = el('text', attrs, g);
    t.textContent = text;
    t.style.paintOrder = 'stroke';
    t.style.stroke = 'var(--bg-1)';
    t.style.strokeWidth = '3px';
    t.style.strokeLinejoin = 'round';
    return t;
  }

  /* Pane corner label: line-key swatches + ink names (per-pane legend) */
  function drawPaneCornerLabel(pane, items) {
    var x = 4;
    items.forEach(function (it) {
      if (it.color) {
        el('line', { x1: x, x2: x + 12, y1: 11, y2: 11, stroke: it.color, 'stroke-width': 2.5, 'stroke-linecap': 'round' }, pane.g);
        x += 16;
      }
      var t = el('text', { 'class': 'axis-text', x: x, y: 14 }, pane.g);
      t.textContent = it.name;
      x += it.name.length * 10.5 + 12;
    });
  }

  /* ------------------------------------------------------------------ */
  /* Crosshair + legend plumbing per chart group                          */
  /* ------------------------------------------------------------------ */
  function makeTooltip(host) {
    var t = div('chart-tooltip', host);
    return {
      show: function (x, y, html) { t.innerHTML = html; t.classList.add('on'); position(x, y); },
      hide: function () { t.classList.remove('on'); },
      el: t
    };
    function position(x, y) {
      var hw = host.clientWidth;
      t.style.left = '';
      t.style.right = '';
      var tw = t.offsetWidth;
      if (x + 16 + tw > hw) { t.style.left = Math.max(0, x - tw - 12) + 'px'; }
      else t.style.left = (x + 16) + 'px';
      t.style.top = clamp(y - 10, 4, host.clientHeight - t.offsetHeight - 4) + 'px';
    }
  }

  /* ==================================================================== */
  /* PaneGroup — linked panes sharing an x range, crosshair, slider       */
  /* ==================================================================== */
  function PaneGroup(host, dates, opts) {
    this.dates = dates;
    this.n = dates.length;
    this.i0 = 0; this.i1 = this.n - 1;
    this.panes = [];
    this.host = host;
    this.opts = opts || {};
    this.hoverIndex = null;
    var self = this;

    this.stage = div('chart-wrap', host);
    this.stage.tabIndex = 0;
    this.stage.setAttribute('role', 'img');
    this.stage.setAttribute('aria-label', opts.ariaLabel || '图表');
    this.svg = el('svg', { 'aria-hidden': 'true' }, this.stage);
    this.legend = div('chart-legend', this.stage);

    this.stage.addEventListener('pointermove', function (e) {
      var r = self.stage.getBoundingClientRect();
      self.setHover(self.xs.inv(e.clientX - r.left - self.padL));
    });
    this.stage.addEventListener('pointerleave', function () { self.setHover(null); });
    this.stage.addEventListener('keydown', function (e) {
      if (self.hoverIndex == null) self.hoverIndex = self.i1;
      if (e.key === 'ArrowLeft') { self.setHover(clamp(self.hoverIndex - 1, self.i0, self.i1)); e.preventDefault(); }
      else if (e.key === 'ArrowRight') { self.setHover(clamp(self.hoverIndex + 1, self.i0, self.i1)); e.preventDefault(); }
      else if (e.key === 'Home') { self.setHover(self.i0); e.preventDefault(); }
      else if (e.key === 'End') { self.setHover(self.i1); e.preventDefault(); }
      else if (e.key === 'Escape') { self.setHover(null); }
    });
    this.padL = 6; this.padR = 54;
  }

  PaneGroup.prototype.addPane = function (pane) {
    pane.group = this;
    this.panes.push(pane);
    return pane;
  };

  PaneGroup.prototype.attachSlider = function (sliderHost, miniSeries, presets) {
    var self = this;
    this.slider = new RangeSlider(sliderHost, this.dates, miniSeries, function (a, b) {
      self.setRange(a, b);
    }, presets);
    return this.slider;
  };

  PaneGroup.prototype.setRange = function (a, b) {
    this.i0 = clamp(Math.min(a, b), 0, this.n - 1);
    this.i1 = clamp(Math.max(a, b), 0, this.n - 1);
    if (this.i1 - this.i0 < 2) this.i1 = Math.min(this.n - 1, this.i0 + 2);
    this.render();
  };

  PaneGroup.prototype.setHover = function (i) {
    this.hoverIndex = i;
    var self = this;
    this.panes.forEach(function (p) { p.drawCross(i); });
    if (this.legendRenderer) this.legendRenderer(i);
    if (i != null) {
      this.stage.setAttribute('aria-label', (this.opts.ariaLabel || '图表') + ' · ' + this.dates[i]);
    }
  };

  PaneGroup.prototype.render = function () {
    var self = this;
    var W = this.host.clientWidth || 800;
    var plotW = Math.max(60, W - this.padL - this.padR);
    this.xs = xScale(this.i0, this.i1, plotW);
    var totalH = 0;
    this.panes.forEach(function (p) { if (!p.hidden) totalH += p.height; });
    this.svg.setAttribute('width', W);
    this.svg.setAttribute('height', totalH);
    while (this.svg.firstChild) this.svg.removeChild(this.svg.firstChild);

    var yOff = 0;
    this.panes.forEach(function (p) {
      if (p.hidden) return;
      p.g = el('g', { transform: 'translate(' + self.padL + ',' + yOff + ')' }, self.svg);
      p.w = plotW; p.h = p.height;
      p.render();
      yOff += p.height;
    });

    /* x axis under last visible pane (edge ticks clamp inward) */
    drawDateAxis(this.svg, this.dates, this.i0, this.i1, this.xs, totalH - 6, plotW);
    if (this.hoverIndex != null) this.setHover(this.hoverIndex);
  };

  /* ---- Pane base ----------------------------------------------------- */
  function Pane(height) { this.height = height; this.hidden = false; }
  Pane.prototype.visibleValues = function (arr) {
    var out = [];
    for (var i = this.group.i0; i <= this.group.i1 && i < arr.length; i++) {
      if (isNum(arr[i])) out.push(arr[i]);
    }
    return out;
  };
  Pane.prototype.yAxis = function (ys, fmt, ticksN) {
    var self = this;
    var ticks = niceTicks(ys.min, ys.max, ticksN || 4);
    ticks.forEach(function (tv) {
      var y = ys.y(tv);
      el('line', { 'class': 'grid-line', x1: 0, x2: self.w, y1: y, y2: y }, self.g);
      var t = el('text', { 'class': 'axis-text', x: self.w + 8, y: y + 3 }, self.g);
      t.textContent = fmt(tv);
    });
  };
  Pane.prototype.linePath = function (arr, ys) {
    var xs = this.group.xs, d = '', started = false;
    for (var i = this.group.i0; i <= this.group.i1 && i < arr.length; i++) {
      var v = arr[i];
      if (!isNum(v)) { started = false; continue; }
      var x = xs.x(i), y = ys.y(v);
      d += started ? 'L' + x.toFixed(1) + ' ' + y.toFixed(1) : 'M' + x.toFixed(1) + ' ' + y.toFixed(1);
      started = true;
    }
    return d;
  };
  Pane.prototype.areaPath = function (arr, ys, baseY) {
    var xs = this.group.xs, g = this.group;
    var d = '', started = false, firstX = 0, lastX = 0;
    for (var i = g.i0; i <= g.i1 && i < arr.length; i++) {
      var v = arr[i];
      if (!isNum(v)) { started = false; continue; }
      var x = xs.x(i), y = ys.y(v);
      if (!started) { firstX = x; d = 'M' + x.toFixed(1) + ' ' + baseY.toFixed(1); }
      d += 'L' + x.toFixed(1) + ' ' + y.toFixed(1);
      lastX = x; started = true;
    }
    if (d) d += 'L' + lastX.toFixed(1) + ' ' + baseY.toFixed(1) + 'Z';
    return d;
  };
  Pane.prototype.drawCross = function (i) {
    if (this.cross) { this.cross.parentNode && this.cross.parentNode.removeChild(this.cross); this.cross = null; }
    if (i == null || !this.g || this.hidden) return;
    var x = this.group.xs.x(clamp(i, this.group.i0, this.group.i1));
    this.cross = el('line', { 'class': 'cross-line', x1: x, x2: x, y1: 0, y2: this.height }, this.g);
  };
  Pane.prototype.zeroLine = function (ys) {
    if (ys.min < 0 && ys.max > 0) {
      var y = ys.y(0);
      el('line', { 'class': 'zero-line', x1: 0, x2: this.w, y1: y, y2: y }, this.g);
    }
  };

  /* ==================================================================== */
  /* RangeSlider — mini-map with draggable window                          */
  /* ==================================================================== */
  function RangeSlider(host, dates, series, onChange, presets) {
    this.host = host; this.dates = dates; this.series = series || [];
    this.onChange = onChange;
    this.n = dates.length;
    this.a = 0; this.b = this.n - 1;
    var self = this;

    this.root = div('range-slider', host);
    this.svg = el('svg', { height: 44, 'aria-hidden': 'true' }, this.root);
    this.maskL = div('rs-mask', this.root);
    this.maskR = div('rs-mask', this.root);
    this.frame = div('rs-frame', this.root);
    this.handleL = div('rs-handle', this.root);
    this.handleR = div('rs-handle', this.root);
    this.handleL.appendChild(div('rs-grip'));
    this.handleR.appendChild(div('rs-grip'));
    this.root.style.height = '44px';

    function drag(handle, isLeft) {
      handle.addEventListener('pointerdown', function (e) {
        e.preventDefault();
        handle.setPointerCapture(e.pointerId);
        function mv(ev) {
          var r = self.root.getBoundingClientRect();
          var frac = clamp((ev.clientX - r.left) / r.width, 0, 1);
          var idx = Math.round(frac * (self.n - 1));
          if (isLeft) self.a = Math.min(idx, self.b - 2); else self.b = Math.max(idx, self.a + 2);
          self.apply(true);
        }
        function up() {
          handle.removeEventListener('pointermove', mv);
          handle.removeEventListener('pointerup', up);
        }
        handle.addEventListener('pointermove', mv);
        handle.addEventListener('pointerup', up);
      });
    }
    drag(this.handleL, true);
    drag(this.handleR, false);

    /* window drag */
    this.svg.addEventListener('pointerdown', function (e) {
      var r = self.root.getBoundingClientRect();
      var frac = (e.clientX - r.left) / r.width;
      var idx = frac * (self.n - 1);
      if (idx > self.a && idx < self.b) {
        e.preventDefault();
        var width = self.b - self.a;
        var startIdx = idx;
        var startA = self.a;
        self.svg.setPointerCapture(e.pointerId);
        function mv(ev) {
          var f2 = clamp((ev.clientX - r.left) / r.width, 0, 1);
          var delta = Math.round((f2 * (self.n - 1)) - startIdx);
          self.a = clamp(startA + delta, 0, self.n - 1 - width);
          self.b = self.a + width;
          self.apply(true);
        }
        function up() {
          self.svg.removeEventListener('pointermove', mv);
          self.svg.removeEventListener('pointerup', up);
        }
        self.svg.addEventListener('pointermove', mv);
        self.svg.addEventListener('pointerup', up);
      } else {
        /* click outside window: center window there */
        var width2 = self.b - self.a;
        self.a = clamp(Math.round(idx - width2 / 2), 0, self.n - 1 - width2);
        self.b = self.a + width2;
        self.apply(true);
      }
    });

    if (presets && presets.host) {
      this.presetBtns = [];
      var defs = [['全部', null], ['1Y', 244], ['6M', 122], ['3M', 61]];
      defs.forEach(function (pd) {
        var b = document.createElement('button');
        b.type = 'button'; b.textContent = pd[0];
        b.addEventListener('click', function () {
          if (pd[1] == null) { self.a = 0; self.b = self.n - 1; }
          else { self.b = self.n - 1; self.a = Math.max(0, self.n - 1 - pd[1]); }
          self.apply(true);
        });
        presets.host.appendChild(b);
        self.presetBtns.push(b);
      });
    }
    this.renderMini();
    this.layoutHandles();
  }

  RangeSlider.prototype.renderMini = function () {
    var W = this.host.clientWidth || 800, H = 44;
    this.svg.setAttribute('width', W);
    this.svg.setAttribute('height', H);
    while (this.svg.firstChild) this.svg.removeChild(this.svg.firstChild);
    var vals = [];
    this.series.forEach(function (s) { s.forEach(function (v) { if (isNum(v)) vals.push(v); }); });
    if (!vals.length) return;
    var v0 = Math.min.apply(null, vals), v1 = Math.max.apply(null, vals);
    var ys = yScale(v0, v1, H - 4, 2);
    var xs = xScale(0, this.n - 1, W);
    var self = this;
    this.series.forEach(function (s, si) {
      var d = '', started = false;
      for (var i = 0; i < s.length; i++) {
        if (!isNum(s[i])) { started = false; continue; }
        d += (started ? 'L' : 'M') + xs.x(i).toFixed(1) + ' ' + ys.y(s[i]).toFixed(1);
        started = true;
      }
      el('path', { d: d, fill: 'none', stroke: si === 0 ? C.accent : C.bench, 'stroke-width': 1, opacity: 0.75 }, self.svg);
    });
  };

  RangeSlider.prototype.layoutHandles = function () {
    var W = this.root.clientWidth || 800;
    var xa = this.a / (this.n - 1) * W, xb = this.b / (this.n - 1) * W;
    this.maskL.style.left = '0'; this.maskL.style.width = xa + 'px';
    this.maskR.style.left = xb + 'px'; this.maskR.style.width = Math.max(0, W - xb) + 'px';
    this.frame.style.left = xa + 'px'; this.frame.style.width = Math.max(0, xb - xa) + 'px';
    this.handleL.style.left = (xa - 5) + 'px';
    this.handleR.style.left = (xb - 5) + 'px';
  };

  RangeSlider.prototype.apply = function (fire) {
    this.layoutHandles();
    if (fire && this.onChange) this.onChange(this.a, this.b);
    if (this.presetBtns) {
      var isAll = this.a === 0 && this.b === this.n - 1;
      this.presetBtns.forEach(function (b, i) { b.classList.toggle('active', i === 0 ? isAll : false); });
    }
  };

  RangeSlider.prototype.resize = function () { this.renderMini(); this.layoutHandles(); };

  /* ==================================================================== */
  /* EQUITY GROUP — equity pane + underwater pane + slider                 */
  /* ==================================================================== */
  function buildEquityGroup(host, sliderHost, presetsHost) {
    var dates = DATA.dates;
    if (!dates || !dates.length) { div('noscript-note', host, '无净值数据'); return null; }
    var eq = DATA.equity || {};
    var seriesDefs = {
      strategy: { name: '策略', color: C.accent, arr: eq.strategy },
      benchmark: { name: DATA.meta.benchmark_label || '基准', color: C.bench, arr: eq.benchmark },
      hs300: { name: '沪深300', color: C.bench, arr: eq.hs300 },
      sse: { name: '上证指数', color: C.bench, arr: eq.sse }
    };
    var benchKey = eq.benchmark ? 'benchmark' : (eq.hs300 ? 'hs300' : (eq.sse ? 'sse' : null));

    var group = new PaneGroup(host, dates, { ariaLabel: '净值曲线与回撤' });

    var eqPane = group.addPane(new Pane(300));
    var ddPane = group.addPane(new Pane(96));

    eqPane.render = function () {
      var p = this, g = this.group;
      var vals = p.visibleValues(seriesDefs.strategy.arr);
      if (benchKey && seriesDefs[benchKey].arr) vals = vals.concat(p.visibleValues(seriesDefs[benchKey].arr));
      if (!vals.length) return;
      var ys = this.ys = yScale(Math.min.apply(null, vals.concat([0])), Math.max.apply(null, vals.concat([0])), p.height - 18, 4);
      p.yAxis(ys, function (v) { return fmtPct(v, 0); });
      p.zeroLine(ys);

      /* worst-3 drawdown shading */
      var ddp = (DATA.drawdown_periods || []).slice(0, 3);
      ddp.forEach(function (per) {
        var ia = dates.indexOf(per.start), ib = dates.indexOf(per.recovery || dates[dates.length - 1]);
        if (ia < 0) return;
        if (ib < 0) ib = dates.length - 1;
        ia = clamp(ia, g.i0, g.i1); ib = clamp(ib, g.i0, g.i1);
        if (ib <= ia) return;
        var x0 = g.xs.x(ia), x1 = g.xs.x(ib);
        el('rect', { x: x0, y: 0, width: x1 - x0, height: p.height - 18, fill: C.down, opacity: 0.05 }, p.g);
      });

      /* benchmark line */
      if (benchKey && seriesDefs[benchKey].arr) {
        el('path', { d: p.linePath(seriesDefs[benchKey].arr, ys), fill: 'none', stroke: C.bench, 'stroke-width': 1.5 }, p.g);
      }
      /* strategy area + line */
      el('path', { d: p.areaPath(seriesDefs.strategy.arr, ys, Math.min(ys.y(0), p.height - 18)), fill: C.accent, opacity: 0.10 }, p.g);
      var line = el('path', { d: p.linePath(seriesDefs.strategy.arr, ys), fill: 'none', stroke: C.accent, 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, p.g);

      /* trade dots on the equity curve (buy below, sell above) */
      (DATA.trade_marks || []).forEach(function (m) {
        if (m.i < g.i0 || m.i > g.i1) return;
        var v = seriesDefs.strategy.arr[m.i];
        if (!isNum(v)) return;
        var x = g.xs.x(m.i), y = ys.y(v);
        var isBuy = m.dir === 'B';
        el('circle', {
          cx: x, cy: isBuy ? y + 9 : y - 9, r: 2.6,
          fill: isBuy ? C.up : C.down, stroke: C.surface, 'stroke-width': 1.2,
          opacity: 0.95
        }, p.g);
      });

      if (!REDUCED && !eqPane._animated) {
        eqPane._animated = true;
        try {
          var len = line.getTotalLength();
          line.style.strokeDasharray = len;
          line.style.strokeDashoffset = len;
          line.getBoundingClientRect();
          line.style.transition = 'stroke-dashoffset 0.9s cubic-bezier(0.4,0,0.2,1)';
          line.style.strokeDashoffset = '0';
          setTimeout(function () { line.style.strokeDasharray = 'none'; }, 1000);
        } catch (e) {}
      }

      /* end labels */
      var sv = lastVisible(seriesDefs.strategy.arr, g);
      if (isNum(sv.v)) {
        el('circle', { cx: g.xs.x(sv.i), cy: ys.y(sv.v), r: 3.5, fill: C.accent, stroke: C.surface, 'stroke-width': 2 }, p.g);
      }
    };

    ddPane.render = function () {
      var p = this, g = this.group;
      var dd = (DATA.drawdown || {}).strategy || [];
      var bdd = (DATA.drawdown || {}).benchmark || [];
      var vals = p.visibleValues(dd);
      if (benchKey && bdd.length) vals = vals.concat(p.visibleValues(bdd));
      if (!vals.length) return;
      var ymin = Math.min.apply(null, vals.concat([0]));
      var ys = this.ys = yScale(ymin, 0, p.height - 4, 2);
      p.yAxis(ys, function (v) { return fmtPct(v, 0); }, 2);
      var zeroY = ys.y(0);
      if (benchKey && bdd.length) {
        el('path', { d: p.linePath(bdd, ys), fill: 'none', stroke: C.bench, 'stroke-width': 1, opacity: 0.85 }, p.g);
      }
      el('path', { d: p.areaPath(dd, ys, zeroY), fill: C.down, opacity: 0.22 }, p.g);
      el('path', { d: p.linePath(dd, ys), fill: 'none', stroke: C.down, 'stroke-width': 1.2 }, p.g);
      el('line', { 'class': 'axis-line', x1: 0, x2: p.w, y1: zeroY, y2: zeroY }, p.g);

      /* worst drawdown trough marker (lives here, clear of the legend) */
      var worst = (DATA.drawdown_periods || [])[0];
      if (worst) {
        var ti = dates.indexOf(worst.trough);
        if (ti >= g.i0 && ti <= g.i1 && isNum(dd[ti])) {
          var tx = g.xs.x(ti), ty = ys.y(dd[ti]);
          el('circle', { cx: tx, cy: ty, r: 4, fill: C.down, stroke: C.surface, 'stroke-width': 2 }, p.g);
          var label = '最大回撤 ' + fmtPct(worst.depth * 100, 1);
          var anchor = tx > p.w - 90 ? 'end' : 'start';
          var lx = tx > p.w - 90 ? tx - 8 : tx + 8;
          haloText({ 'class': 'axis-text', x: lx, y: ty - 6, 'text-anchor': anchor }, label, p.g);
        }
      }
    };

    group.legendRenderer = function (i) {
      var idx = i == null ? group.i1 : i;
      var h = '<span class="lg-item"><span class="lg-name">' + dates[idx] + '</span></span>';
      h += legendItem(C.accent, '策略', fmtSignedPct(valAt(seriesDefs.strategy.arr, idx)));
      if (benchKey && seriesDefs[benchKey].arr) {
        h += legendItem(C.bench, seriesDefs[benchKey].name, fmtPctValOrDash(valAt(seriesDefs[benchKey].arr, idx)));
      }
      var dd = (DATA.drawdown || {}).strategy || [];
      h += legendItem(C.down, '回撤', fmtPctValOrDash(valAt(dd, idx)));
      group.legend.innerHTML = h;
    };
    group.legendRenderer(null);

    function lastVisible(arr, g) {
      for (var i = g.i1; i >= g.i0; i--) if (isNum(arr[i])) return { v: arr[i], i: i };
      return { v: null, i: g.i1 };
    }
    function valAt(arr, i) { return i >= 0 && i < arr.length ? arr[i] : null; }
    function legendItem(color, name, valHtml) {
      return '<span class="lg-item"><span class="lg-key" style="background:' + color + '"></span>' +
        '<span class="lg-name">' + name + '</span><span class="lg-val">' + valHtml + '</span></span>';
    }
    function fmtPctValOrDash(v) { return isNum(v) ? fmtSignedPct(v) : '—'; }

    /* benchmark switcher */
    var switchHost = document.getElementById('benchSwitch');
    if (switchHost) {
      var opts = [];
      if (eq.benchmark) opts.push(['benchmark', DATA.meta.benchmark_label || '基准']);
      if (eq.hs300 && DATA.meta.benchmark_code !== '000300') opts.push(['hs300', '沪深300']);
      if (eq.sse && DATA.meta.benchmark_code !== '000001') opts.push(['sse', '上证指数']);
      opts.push(['none', '隐藏']);
      if (opts.length > 2) {
        opts.forEach(function (o) {
          var b = document.createElement('button');
          b.type = 'button'; b.textContent = o[1];
          b.dataset.bench = o[0];
          if (o[0] === benchKey) b.classList.add('active');
          b.addEventListener('click', function () {
            benchKey = o[0] === 'none' ? null : o[0];
            switchHost.querySelectorAll('button').forEach(function (x) { x.classList.toggle('active', x === b); });
            group.render();
            group.legendRenderer(group.hoverIndex);
          });
          switchHost.appendChild(b);
        });
      }
    }

    var slider = null;
    if (sliderHost) {
      var mini = [seriesDefs.strategy.arr];
      group.attachSlider(sliderHost, mini, { host: presetsHost });
      slider = group.slider;
    }

    group.render();
    return group;
  }

  /* ==================================================================== */
  /* KLINE GROUP                                                           */
  /* ==================================================================== */
  function buildKlineGroup(host, sliderHost, symbol) {
    var kd = (DATA.kline || {})[symbol];
    if (!kd || !kd.dates || !kd.dates.length) {
      div('noscript-note', host, '该标的无 K 线数据');
      return null;
    }
    var dates = kd.dates;
    var toggles = { ma: true, bb: false, macd: false, rsi: false };

    var group = new PaneGroup(host, dates, { ariaLabel: symbol + ' K线图' });
    var main = group.addPane(new Pane(300));
    var macdPane = group.addPane(new Pane(90));
    var rsiPane = group.addPane(new Pane(80));
    macdPane.hidden = true; rsiPane.hidden = true;

    main.render = function () {
      var p = this, g = this.group;
      var lo = Infinity, hi = -Infinity;
      for (var i = g.i0; i <= g.i1 && i < dates.length; i++) {
        if (isNum(kd.l[i]) && kd.l[i] < lo) lo = kd.l[i];
        if (isNum(kd.h[i]) && kd.h[i] > hi) hi = kd.h[i];
      }
      if (!isFinite(lo)) return;
      var volH = Math.round(p.height * 0.18);
      var priceH = p.height - volH - 14;
      var ys = this.ys = yScale(lo, hi, priceH, 4);
      p.yAxis(ys, function (v) { return v.toFixed(2); });

      /* BOLL bands */
      if (toggles.bb && kd.bb_u) {
        ['bb_u', 'bb_m', 'bb_l'].forEach(function (k, idx) {
          el('path', { d: p.linePath(kd[k], ys), fill: 'none', stroke: C.ink4, 'stroke-width': 1, opacity: idx === 1 ? 0.9 : 0.6 }, p.g);
        });
      }
      /* S/R removed from default view; BB only on toggle */

      /* candles */
      var step = g.xs.step;
      var bw = Math.max(1, Math.min(18, step * 0.68));
      for (var i = g.i0; i <= g.i1 && i < dates.length; i++) {
        if (!isNum(kd.o[i]) || !isNum(kd.c[i])) continue;
        var x = g.xs.x(i);
        var up = kd.c[i] >= kd.o[i];
        var col = up ? C.up : C.down;
        /* wick */
        if (isNum(kd.h[i]) && isNum(kd.l[i])) {
          el('line', { x1: x, x2: x, y1: ys.y(kd.h[i]), y2: ys.y(kd.l[i]), stroke: up ? C.up : C.down, 'stroke-width': 1 }, p.g);
        }
        var yo = ys.y(kd.o[i]), yc = ys.y(kd.c[i]);
        var top = Math.min(yo, yc), hgt = Math.max(1, Math.abs(yc - yo));
        el('rect', { x: x - bw / 2, y: top, width: bw, height: hgt, fill: up ? C.up : C.down, rx: bw > 4 ? 1 : 0 }, p.g);
        /* limit-up (触及涨停): gold outline — A-share vernacular marker */
        if (kd.lim && kd.lim[i]) {
          var limR = el('rect', {
            x: x - bw / 2 - 1, y: top - 1, width: bw + 2, height: hgt + 2,
            fill: 'none', stroke: C.warn, 'stroke-width': 1
          }, p.g);
          var limT = el('title', {}, limR);
          limT.textContent = '触及涨停（按板块涨跌幅阈值估算）';
        }
      }

      /* MA ordinal ramp */
      if (toggles.ma) {
        [['ma5', C.ma5], ['ma20', C.ma20], ['ma60', C.ma60]].forEach(function (mk) {
          if (kd[mk[0]]) el('path', { d: p.linePath(kd[mk[0]], ys), fill: 'none', stroke: mk[1], 'stroke-width': 1.2, opacity: 0.95 }, p.g);
        });
      }

      /* volume sub-band */
      var vmax = 0;
      for (var j = g.i0; j <= g.i1 && j < dates.length; j++) if (isNum(kd.v[j]) && kd.v[j] > vmax) vmax = kd.v[j];
      var vTop = p.height - 14 - volH;
      el('line', { 'class': 'axis-line', x1: 0, x2: p.w, y1: vTop, y2: vTop }, p.g);
      if (vmax > 0) {
        for (var k = g.i0; k <= g.i1 && k < dates.length; k++) {
          if (!isNum(kd.v[k])) continue;
          var vx = g.xs.x(k);
          var vh = kd.v[k] / vmax * (volH - 4);
          var vup = isNum(kd.c[k]) && isNum(kd.o[k]) ? kd.c[k] >= kd.o[k] : true;
          el('rect', { x: vx - bw / 2, y: p.height - 14 - vh, width: bw, height: vh, fill: vup ? C.up : C.down, opacity: 0.4 }, p.g);
        }
      }

      /* trade markers */
      (kd.markers || []).forEach(function (m) {
        if (m.i < g.i0 || m.i > g.i1) return;
        var x = g.xs.x(m.i);
        var isBuy = m.dir === 'B';
        var ref = isBuy
          ? (isNum(kd.l[m.i]) ? ys.y(kd.l[m.i]) : priceH)
          : (isNum(kd.h[m.i]) ? ys.y(kd.h[m.i]) : 0);
        var y = isBuy ? ref + 14 : ref - 14;
        var path = isBuy
          ? 'M' + x + ' ' + (y - 5) + 'L' + (x - 4.5) + ' ' + (y + 3) + 'L' + (x + 4.5) + ' ' + (y + 3) + 'Z'
          : 'M' + x + ' ' + (y + 5) + 'L' + (x - 4.5) + ' ' + (y - 3) + 'L' + (x + 4.5) + ' ' + (y - 3) + 'Z';
        var mk = el('path', { d: path, fill: isBuy ? C.up : C.down, stroke: C.surface, 'stroke-width': 1.5 }, p.g);
        mk.style.cursor = 'default';
        var title = el('title', {}, mk);
        title.textContent = m.text || '';
      });
    };

    macdPane.render = function () {
      var p = this, g = this.group;
      var vals = p.visibleValues(kd.macd_dif || []).concat(p.visibleValues(kd.macd_dea || []), p.visibleValues(kd.macd_hist || []));
      if (!vals.length) return;
      var mx = Math.max.apply(null, vals.map(Math.abs));
      var ys = this.ys = yScale(-mx, mx, p.height - 4, 2);
      p.yAxis(ys, function (v) { return v.toFixed(3); }, 2);
      p.zeroLine(ys);
      var step = g.xs.step, bw = Math.max(1, Math.min(10, step * 0.5));
      for (var i = g.i0; i <= g.i1 && i < dates.length; i++) {
        var hv = (kd.macd_hist || [])[i];
        if (!isNum(hv)) continue;
        var x = g.xs.x(i), y0 = ys.y(0), y1 = ys.y(hv);
        el('rect', { x: x - bw / 2, y: Math.min(y0, y1), width: bw, height: Math.max(1, Math.abs(y1 - y0)), fill: hv >= 0 ? C.up : C.down, opacity: 0.65 }, p.g);
      }
      el('path', { d: p.linePath(kd.macd_dif || [], ys), fill: 'none', stroke: C.ma20, 'stroke-width': 1.2 }, p.g);
      el('path', { d: p.linePath(kd.macd_dea || [], ys), fill: 'none', stroke: C.bench, 'stroke-width': 1.2 }, p.g);
      drawPaneCornerLabel(p, [
        { color: null, name: 'MACD(12,26,9)' },
        { color: C.ma20, name: 'DIF' },
        { color: C.bench, name: 'DEA' }
      ]);
    };

    rsiPane.render = function () {
      var p = this, g = this.group;
      var vals = p.visibleValues(kd.rsi || []);
      if (!vals.length) return;
      var ys = this.ys = yScale(0, 100, p.height - 4, 2);
      p.yAxis(ys, function (v) { return v.toFixed(0); }, 2);
      [30, 70].forEach(function (lv) {
        el('line', { 'class': 'ref-line', x1: 0, x2: p.w, y1: ys.y(lv), y2: ys.y(lv) }, p.g);
      });
      el('path', { d: p.linePath(kd.rsi || [], ys), fill: 'none', stroke: C.warn, 'stroke-width': 1.3 }, p.g);
      drawPaneCornerLabel(p, [{ color: null, name: 'RSI(14)' }]);
    };

    group.legendRenderer = function (i) {
      var idx = i == null ? group.i1 : i;
      function v(a) { return idx >= 0 && idx < a.length ? a[idx] : null; }
      var o = v(kd.o), h2 = v(kd.h), l = v(kd.l), c2 = v(kd.c), vol = v(kd.v);
      var chg = isNum(c2) && isNum(o) ? (c2 - o) / o * 100 : null;
      var htm = '<span class="lg-item"><span class="lg-name">' + symbol.replace(/\.(XSHG|XSHE)$/, '') + ' · ' + dates[idx] + '</span></span>';
      htm += '<span class="lg-item"><span class="lg-name">开</span><span class="lg-val">' + fmtNum(o) + '</span></span>';
      htm += '<span class="lg-item"><span class="lg-name">高</span><span class="lg-val">' + fmtNum(h2) + '</span></span>';
      htm += '<span class="lg-item"><span class="lg-name">低</span><span class="lg-val">' + fmtNum(l) + '</span></span>';
      htm += '<span class="lg-item"><span class="lg-name">收</span><span class="lg-val ' + clsDelta(chg) + '">' + fmtNum(c2) + '</span></span>';
      htm += '<span class="lg-item"><span class="lg-name">幅</span><span class="lg-val ' + clsDelta(chg) + '">' + fmtSignedPct(chg) + '</span></span>';
      htm += '<span class="lg-item"><span class="lg-name">量</span><span class="lg-val">' + fmtVol(vol) + '</span></span>';
      if (toggles.ma) {
        [['MA5', C.ma5, 'ma5'], ['MA20', C.ma20, 'ma20'], ['MA60', C.ma60, 'ma60']].forEach(function (mk) {
          var mv = v(kd[mk[2]] || []);
          htm += '<span class="lg-item"><span class="lg-key" style="background:' + mk[1] + '"></span>' +
            '<span class="lg-name">' + mk[0] + '</span><span class="lg-val">' + fmtNum(mv) + '</span></span>';
        });
      }
      group.legend.innerHTML = htm;
    };
    group.legendRenderer(null);

    if (sliderHost) {
      group.attachSlider(sliderHost, [kd.c], null);
    }

    group.setToggle = function (name, on) {
      toggles[name] = on;
      if (name === 'macd') macdPane.hidden = !on;
      if (name === 'rsi') rsiPane.hidden = !on;
      group.render();
      group.legendRenderer(group.hoverIndex);
    };
    group.getToggles = function () { return toggles; };

    group.render();
    return group;
  }

  /* ==================================================================== */
  /* Simple standalone charts                                              */
  /* ==================================================================== */

  /* Generic single-series line chart with crosshair + tooltip */
  function simpleLineChart(host, dates, series, opts) {
    opts = opts || {};
    if (!series || !series.length || !series[0].arr.length) { div('noscript-note', host, '数据不足'); return; }
    var wrap = div('chart-wrap', host);
    wrap.tabIndex = 0;
    wrap.setAttribute('role', 'img');
    wrap.setAttribute('aria-label', opts.ariaLabel || '折线图');
    var H = opts.height || 150, padL = 6, padR = 54;
    var svg = el('svg', {}, wrap);
    var tooltip = makeTooltip(wrap);
    var cross = null, hoverI = null;

    var xs = xScale(0, dates.length - 1, 1);
    var ys = null;

    function render() {
      var W = wrap.clientWidth || 600;
      var plotW = W - padL - padR;
      xs = xScale(0, dates.length - 1, plotW);
      svg.setAttribute('width', W);
      svg.setAttribute('height', H);
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      var g = el('g', { transform: 'translate(' + padL + ',0)' }, svg);

      var vals = [];
      series.forEach(function (s) { s.arr.forEach(function (v) { if (isNum(v)) vals.push(v); }); });
      if (!vals.length) return;
      var v0 = Math.min.apply(null, vals), v1 = Math.max.apply(null, vals);
      if (opts.includeZero) { v0 = Math.min(v0, 0); v1 = Math.max(v1, 0); }
      ys = yScale(opts.yMin != null ? opts.yMin : v0, opts.yMax != null ? opts.yMax : v1, H - 18, 4);

      var tickVals = niceTicks(ys.min, ys.max, 3);
      tickVals.forEach(function (tv) {
        var y = ys.y(tv);
        el('line', { 'class': 'grid-line', x1: 0, x2: plotW, y1: y, y2: y }, g);
        var t = el('text', { 'class': 'axis-text', x: plotW + 8, y: y + 3 }, g);
        t.textContent = opts.fmtY ? opts.fmtY(tv) : fmtNum(tv);
      });
      if (ys.min < 0 && ys.max > 0) el('line', { 'class': 'zero-line', x1: 0, x2: plotW, y1: ys.y(0), y2: ys.y(0) }, g);
      (opts.refLines || []).forEach(function (rl) {
        var y = ys.y(rl.v);
        el('line', { 'class': 'ref-line', x1: 0, x2: plotW, y1: y, y2: y }, g);
        /* skip the label when a gridline already prints the same value */
        var dupe = tickVals.some(function (tv) { return Math.abs(tv - rl.v) < (ys.max - ys.min) * 0.02; });
        if (!dupe) {
          var t = el('text', { 'class': 'axis-text', x: plotW + 8, y: y + 3 }, g);
          t.textContent = rl.label;
        }
      });
      drawDateAxis(g, dates, 0, dates.length - 1, xs, H - 4, plotW);

      series.forEach(function (s) {
        var pane = { group: { xs: xs, i0: 0, i1: dates.length - 1 } };
        var d = linePathRaw(s.arr, xs, ys);
        if (s.area) {
          el('path', { d: d + areaCloseRaw(s.arr, xs, ys, Math.min(ys.y(0), H - 18)), fill: s.color, opacity: 0.12 }, g);
        }
        el('path', { d: d, fill: 'none', stroke: s.color, 'stroke-width': s.width || 1.6, 'stroke-linejoin': 'round' }, g);
      });
    }

    function linePathRaw(arr, xs2, ys2) {
      var d = '', started = false;
      for (var i = 0; i < arr.length; i++) {
        if (!isNum(arr[i])) { started = false; continue; }
        d += (started ? 'L' : 'M') + xs2.x(i).toFixed(1) + ' ' + ys2.y(arr[i]).toFixed(1);
        started = true;
      }
      return d;
    }
    function areaCloseRaw(arr, xs2, ys2, baseY) {
      var lastX = 0, firstX = 0, started = false;
      for (var i = 0; i < arr.length; i++) {
        if (!isNum(arr[i])) { started = false; continue; }
        if (!started) firstX = xs2.x(i);
        lastX = xs2.x(i); started = true;
      }
      return 'L' + lastX.toFixed(1) + ' ' + baseY + 'L' + firstX.toFixed(1) + ' ' + baseY + 'Z';
    }

    wrap.addEventListener('pointermove', function (e) {
      var r = wrap.getBoundingClientRect();
      var i = xs.inv(e.clientX - r.left - padL);
      hoverI = i;
      if (cross) cross.remove();
      cross = el('line', { 'class': 'cross-line', x1: padL + xs.x(i), x2: padL + xs.x(i), y1: 0, y2: H - 18 }, svg);
      var rows = '<div class="tt-title">' + dates[i] + '</div>';
      series.forEach(function (s) {
        var v = s.arr[i];
        rows += '<div class="tt-row"><span class="tt-key" style="background:' + s.color + '"></span>' +
          '<span class="tt-name">' + s.name + '</span>' +
          '<span class="tt-value ' + (opts.signed ? clsDelta(v) : '') + '">' + (opts.fmtV ? opts.fmtV(v) : fmtNum(v)) + '</span></div>';
      });
      tooltip.show(e.clientX - r.left, e.clientY - r.top, rows);
    });
    wrap.addEventListener('pointerleave', function () { if (cross) { cross.remove(); cross = null; } tooltip.hide(); });

    render();
    observeResize(wrap, render);
  }

  /* Diverging area chart (excess return) */
  function divergingAreaChart(host, dates, arr, opts) {
    opts = opts || {};
    if (!arr || !arr.length) { div('noscript-note', host, '数据不足'); return; }
    var wrap = div('chart-wrap', host);
    wrap.tabIndex = 0;
    wrap.setAttribute('role', 'img');
    wrap.setAttribute('aria-label', opts.ariaLabel || '超额收益曲线');
    var H = opts.height || 170, padL = 6, padR = 54;
    var svg = el('svg', {}, wrap);
    var tooltip = makeTooltip(wrap);
    var cross = null;
    var xs, ys;

    function render() {
      var W = wrap.clientWidth || 600;
      var plotW = W - padL - padR;
      xs = xScale(0, dates.length - 1, plotW);
      svg.setAttribute('width', W); svg.setAttribute('height', H);
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      var g = el('g', { transform: 'translate(' + padL + ',0)' }, svg);

      var vals = arr.filter(isNum);
      if (!vals.length) return;
      var mx = Math.max.apply(null, vals.map(Math.abs));
      ys = yScale(-mx, mx, H - 18, 4);

      niceTicks(-mx, mx, 4).forEach(function (tv) {
        var y = ys.y(tv);
        el('line', { 'class': 'grid-line', x1: 0, x2: plotW, y1: y, y2: y }, g);
        var t = el('text', { 'class': 'axis-text', x: plotW + 8, y: y + 3 }, g);
        t.textContent = fmtPct(tv, 0);
      });
      el('line', { 'class': 'zero-line', x1: 0, x2: plotW, y1: ys.y(0), y2: ys.y(0) }, g);
      drawDateAxis(g, dates, 0, dates.length - 1, xs, H - 4, plotW);

      /* split into positive/negative area segments with zero-crossing interp */
      var segs = splitAtZero(arr);
      segs_draw(g, segs, xs, ys);
      function segs_draw(g2, segs2, xs2, ys2) {
        segs2.forEach(function (sg) {
          var col = sg.sign >= 0 ? C.up : C.down;
          var baseY = ys2.y(0);
          var d = '';
          sg.pts.forEach(function (pt, k) {
            d += (k === 0 ? 'M' : 'L') + xs2.x(pt.i).toFixed(1) + ' ' + ys2.y(pt.v).toFixed(1);
          });
          var first = sg.pts[0], last = sg.pts[sg.pts.length - 1];
          var area = d + 'L' + xs2.x(last.i).toFixed(1) + ' ' + baseY + 'L' + xs2.x(first.i).toFixed(1) + ' ' + baseY + 'Z';
          el('path', { d: area, fill: col, opacity: 0.14 }, g2);
          el('path', { d: d, fill: 'none', stroke: col, 'stroke-width': 1.6 }, g2);
        });
      }
    }

    function splitAtZero(a) {
      var out = [], cur = null;
      for (var i = 0; i < a.length; i++) {
        var v = a[i];
        if (!isNum(v)) { cur = null; continue; }
        var sign = v >= 0 ? 1 : -1;
        if (cur && cur.sign !== sign && cur.pts.length) {
          var prev = cur.pts[cur.pts.length - 1];
          var frac = Math.abs(prev.v) / (Math.abs(prev.v) + Math.abs(v));
          var xi = prev.i + frac;
          cur.pts.push({ i: xi, v: 0 });
          out.push(cur);
          cur = { sign: sign, pts: [{ i: xi, v: 0 }, { i: i, v: v }] };
        } else {
          if (!cur) cur = { sign: sign, pts: [] };
          cur.pts.push({ i: i, v: v });
        }
      }
      if (cur) out.push(cur);
      return out;
    }

    wrap.addEventListener('pointermove', function (e) {
      var r = wrap.getBoundingClientRect();
      var i = xs.inv(e.clientX - r.left - padL);
      if (cross) cross.remove();
      cross = el('line', { 'class': 'cross-line', x1: padL + xs.x(i), x2: padL + xs.x(i), y1: 0, y2: H - 18 }, svg);
      var v = arr[i];
      tooltip.show(e.clientX - r.left, e.clientY - r.top,
        '<div class="tt-title">' + dates[i] + '</div>' +
        '<div class="tt-row"><span class="tt-name">累计超额</span><span class="tt-value ' + clsDelta(v) + '">' + fmtSignedPct(v) + '</span></div>');
    });
    wrap.addEventListener('pointerleave', function () { if (cross) { cross.remove(); cross = null; } tooltip.hide(); });

    render();
    observeResize(wrap, render);
  }

  /* Stacked area (allocation) */
  function allocationChart(host, dates, cash, invested) {
    if (!dates || !dates.length || !cash.length) { div('noscript-note', host, '数据不足'); return; }
    var wrap = div('chart-wrap', host);
    wrap.tabIndex = 0;
    wrap.setAttribute('role', 'img');
    wrap.setAttribute('aria-label', '资产构成：持仓市值与现金堆叠面积图');
    var H = 170, padL = 6, padR = 62;
    var svg = el('svg', {}, wrap);
    var tooltip = makeTooltip(wrap);
    var cross = null;
    var xs, ys;

    function render() {
      var W = wrap.clientWidth || 600;
      var plotW = W - padL - padR;
      xs = xScale(0, dates.length - 1, plotW);
      svg.setAttribute('width', W); svg.setAttribute('height', H);
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      var g = el('g', { transform: 'translate(' + padL + ',0)' }, svg);

      var v1 = 0;
      for (var i = 0; i < dates.length; i++) {
        var tot = (isNum(cash[i]) ? cash[i] : 0) + (isNum(invested[i]) ? invested[i] : 0);
        if (tot > v1) v1 = tot;
      }
      if (v1 <= 0) return;
      ys = yScale(0, v1, H - 18, 4);

      niceTicks(0, v1, 3).forEach(function (tv) {
        var y = ys.y(tv);
        el('line', { 'class': 'grid-line', x1: 0, x2: plotW, y1: y, y2: y }, g);
        var t = el('text', { 'class': 'axis-text', x: plotW + 8, y: y + 3 }, g);
        t.textContent = fmtMoney(tv);
      });
      drawDateAxis(g, dates, 0, dates.length - 1, xs, H - 4, plotW);

      /* cash bottom (neutral), invested top (accent) */
      function stackPath(bottomArr, topArr) {
        var d = '', started = false, i;
        for (i = 0; i < dates.length; i++) {
          var tv2 = (isNum(bottomArr[i]) ? bottomArr[i] : 0) + (isNum(topArr[i]) ? topArr[i] : 0);
          d += (started ? 'L' : 'M') + xs.x(i).toFixed(1) + ' ' + ys.y(tv2).toFixed(1);
          started = true;
        }
        for (i = dates.length - 1; i >= 0; i--) {
          var bv = isNum(bottomArr[i]) ? bottomArr[i] : 0;
          d += 'L' + xs.x(i).toFixed(1) + ' ' + ys.y(bv).toFixed(1);
        }
        return d + 'Z';
      }
      var zeros = dates.map(function () { return 0; });
      el('path', { d: stackPath(zeros, cash), fill: C.ink4, opacity: 0.45, stroke: 'none' }, g);
      el('path', { d: stackPath(cash, invested), fill: C.accent, opacity: 0.45, stroke: 'none' }, g);
      /* position ratio line on same axis? No dual axis — ratio shown in tooltip only */
    }

    wrap.addEventListener('pointermove', function (e) {
      var r = wrap.getBoundingClientRect();
      var i = xs.inv(e.clientX - r.left - padL);
      if (cross) cross.remove();
      cross = el('line', { 'class': 'cross-line', x1: padL + xs.x(i), x2: padL + xs.x(i), y1: 0, y2: H - 18 }, svg);
      var c2 = cash[i], inv = invested[i];
      var tot = (isNum(c2) ? c2 : 0) + (isNum(inv) ? inv : 0);
      var ratio = tot > 0 && isNum(inv) ? inv / tot * 100 : null;
      tooltip.show(e.clientX - r.left, e.clientY - r.top,
        '<div class="tt-title">' + dates[i] + '</div>' +
        '<div class="tt-row"><span class="tt-key" style="background:' + C.accent + '"></span><span class="tt-name">持仓市值</span><span class="tt-value">' + fmtMoney(inv) + '</span></div>' +
        '<div class="tt-row"><span class="tt-key" style="background:' + C.ink4 + '"></span><span class="tt-name">现金</span><span class="tt-value">' + fmtMoney(c2) + '</span></div>' +
        '<div class="tt-row"><span class="tt-name">仓位</span><span class="tt-value">' + fmtPct(ratio, 1) + '</span></div>');
    });
    wrap.addEventListener('pointerleave', function () { if (cross) { cross.remove(); cross = null; } tooltip.hide(); });

    render();
    observeResize(wrap, render);
  }

  /* Annual grouped bars + excess strip */
  function annualChart(host, rows) {
    if (!rows || !rows.length) { div('noscript-note', host, '数据不足'); return; }
    var wrap = div('chart-wrap', host);
    wrap.setAttribute('role', 'img');
    wrap.setAttribute('aria-label', '年度收益对比柱状图');
    var H = 190, padL = 6, padR = 54, excessH = 46;
    var svg = el('svg', {}, wrap);
    var tooltip = makeTooltip(wrap);
    var hitRects = [];

    function render() {
      var W = wrap.clientWidth || 500;
      var plotW = W - padL - padR;
      var mainH = H - excessH - 22;
      svg.setAttribute('width', W); svg.setAttribute('height', H);
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      hitRects = [];
      var g = el('g', { transform: 'translate(' + padL + ',0)' }, svg);

      var v0 = 0, v1 = 0, e1 = 0;
      rows.forEach(function (r) {
        v0 = Math.min(v0, r.strategy * 100, (r.benchmark || 0) * 100, 0);
        v1 = Math.max(v1, r.strategy * 100, (r.benchmark || 0) * 100, 0);
        e1 = Math.max(e1, Math.abs((r.excess || 0) * 100));
      });
      var ys = yScale(v0, v1, mainH, 4);
      niceTicks(v0, v1, 4).forEach(function (tv) {
        var y = ys.y(tv);
        el('line', { 'class': 'grid-line', x1: 0, x2: plotW, y1: y, y2: y }, g);
        var t = el('text', { 'class': 'axis-text', x: plotW + 8, y: y + 3 }, g);
        t.textContent = fmtPct(tv, 0);
      });
      el('line', { 'class': 'zero-line', x1: 0, x2: plotW, y1: ys.y(0), y2: ys.y(0) }, g);

      var slotW = plotW / rows.length;
      var barW = Math.min(24, slotW * 0.26);
      rows.forEach(function (r, i) {
        var cx = slotW * (i + 0.5);
        var y0 = ys.y(0);
        /* strategy bar */
        var sv = r.strategy * 100;
        var y1b = ys.y(sv);
        var sh = Math.max(1, Math.abs(y1b - y0));
        el('path', { d: barRectPath(cx - barW - 2, Math.min(y0, y1b), barW, sh, sv >= 0), fill: C.accent }, g);
        /* benchmark bar */
        if (r.benchmark != null) {
          var bv = r.benchmark * 100;
          var y2 = ys.y(bv);
          var bh = Math.max(1, Math.abs(y2 - y0));
          el('path', { d: barRectPath(cx + 2, Math.min(y0, y2), barW, bh, bv >= 0), fill: C.bench }, g);
        }
        /* value labels at bar tips (below the bar when negative) */
        var lt = el('text', {
          'class': 'axis-text', x: cx - barW / 2 - 2,
          y: sv >= 0 ? Math.min(y0, y1b) - 4 : Math.max(y0, y1b) + 11,
          'text-anchor': 'middle'
        }, g);
        lt.textContent = fmtPct(sv, 1);
        if (r.benchmark != null) {
          var bv2 = r.benchmark * 100;
          var bt = el('text', {
            'class': 'axis-text', x: cx + 2 + barW / 2,
            y: bv2 >= 0 ? Math.min(y0, ys.y(bv2)) - 4 : Math.max(y0, ys.y(bv2)) + 11,
            'text-anchor': 'middle', opacity: 0.8
          }, g);
          bt.textContent = fmtPct(bv2, 1);
        }
        /* year label */
        var yl = el('text', { 'class': 'axis-text', x: cx, y: mainH + 14, 'text-anchor': 'middle' }, g);
        yl.textContent = r.year;

        /* excess strip bar */
        var ev = (r.excess || 0) * 100;
        var eys = yScale(-e1, e1, excessH, 0);
        var ey0 = eys.y(0), ey1 = eys.y(ev);
        el('rect', {
          x: cx - barW - 2, y: mainH + 20 + Math.min(ey0, ey1), width: barW * 2 + 4,
          height: Math.max(1, Math.abs(ey1 - ey0)), fill: ev >= 0 ? C.up : C.down, opacity: 0.75, rx: 2
        }, g);

        /* hit target */
        var hr = el('rect', { x: slotW * i, y: 0, width: slotW, height: H, fill: 'transparent', tabindex: '-1' }, g);
        (function (rr) {
          hr.addEventListener('pointermove', function (e) {
            var rc = wrap.getBoundingClientRect();
            tooltip.show(e.clientX - rc.left, e.clientY - rc.top,
              '<div class="tt-title">' + rr.year + '</div>' +
              '<div class="tt-row"><span class="tt-key" style="background:' + C.accent + '"></span><span class="tt-name">策略</span><span class="tt-value ' + clsDelta(rr.strategy) + '">' + fmtPctFrac(rr.strategy, 2) + '</span></div>' +
              (rr.benchmark != null ? '<div class="tt-row"><span class="tt-key" style="background:' + C.bench + '"></span><span class="tt-name">基准</span><span class="tt-value ' + clsDelta(rr.benchmark) + '">' + fmtPctFrac(rr.benchmark, 2) + '</span></div>' : '') +
              '<div class="tt-row"><span class="tt-name">超额</span><span class="tt-value ' + clsDelta(rr.excess) + '">' + fmtPctFrac(rr.excess, 2) + '</span></div>');
          });
          hr.addEventListener('pointerleave', function () { tooltip.hide(); });
        })(r);
      });
      /* excess strip label + zero */
      var eysL = yScale(-e1, e1, excessH, 0);
      el('line', { 'class': 'zero-line', x1: 0, x2: plotW, y1: mainH + 20 + eysL.y(0), y2: mainH + 20 + eysL.y(0) }, g);
      var elab = el('text', { 'class': 'axis-text', x: 0, y: mainH + 20 - 4 }, g);
      elab.textContent = '超额';
    }

    wrap.addEventListener('pointerleave', function () { tooltip.hide(); });
    render();
    observeResize(wrap, render);
  }

  /* Return-distribution histogram */
  function distChart(host, bins, stats) {
    if (!bins || !bins.length) { div('noscript-note', host, '数据不足'); return; }
    var wrap = div('chart-wrap', host);
    wrap.setAttribute('role', 'img');
    wrap.setAttribute('aria-label', '日收益分布直方图');
    var H = 170, padL = 6, padR = 54;
    var svg = el('svg', {}, wrap);
    var tooltip = makeTooltip(wrap);

    function render() {
      var W = wrap.clientWidth || 500;
      var plotW = W - padL - padR;
      svg.setAttribute('width', W); svg.setAttribute('height', H);
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      var g = el('g', { transform: 'translate(' + padL + ',0)' }, svg);

      var x0 = bins[0].x0, x1 = bins[bins.length - 1].x1;
      var cmax = 0;
      bins.forEach(function (b) { if (b.count > cmax) cmax = b.count; });
      var ys = yScale(0, cmax, H - 22, 4);
      function xx(v) { return (v - x0) / (x1 - x0) * plotW; }

      /* count axis */
      niceTicks(0, cmax, 3).forEach(function (tv) {
        var y = ys.y(tv);
        el('line', { 'class': 'grid-line', x1: 0, x2: plotW, y1: y, y2: y }, g);
        var t = el('text', { 'class': 'axis-text', x: plotW + 8, y: y + 3 }, g);
        t.textContent = fmtInt(tv);
      });
      /* value axis ticks: 0% + edges, clamped inward */
      [x0, 0, x1].forEach(function (v) {
        if (v < x0 || v > x1) return;
        var x = xx(v);
        var anchor = 'middle';
        if (x < 26) anchor = 'start';
        else if (x > plotW - 26) anchor = 'end';
        var t = el('text', { 'class': 'axis-text', x: x, y: H - 6, 'text-anchor': anchor }, g);
        t.textContent = (v * 100).toFixed(1) + '%';
      });
      el('line', { 'class': 'zero-line', x1: xx(0), x2: xx(0), y1: 0, y2: H - 22 }, g);

      var bw = plotW / bins.length;
      bins.forEach(function (b) {
        var mid = (b.x0 + b.x1) / 2;
        var col = mid < 0 ? C.down : C.up;
        var y = ys.y(b.count);
        var r = el('rect', {
          x: xx(b.x0) + 1, y: y, width: Math.max(1, bw - 2), height: Math.max(1, ys.y(0) - y),
          fill: col, opacity: 0.82, rx: 1, tabindex: '-1'
        }, g);
        r.addEventListener('pointermove', function (e) {
          var rc = wrap.getBoundingClientRect();
          tooltip.show(e.clientX - rc.left, e.clientY - rc.top,
            '<div class="tt-row"><span class="tt-name">区间</span><span class="tt-value">' + (b.x0 * 100).toFixed(2) + '% ~ ' + (b.x1 * 100).toFixed(2) + '%</span></div>' +
            '<div class="tt-row"><span class="tt-name">天数</span><span class="tt-value">' + b.count + '</span></div>');
        });
        r.addEventListener('pointerleave', function () { tooltip.hide(); });
      });

      /* mean marker */
      if (stats && isNum(stats.mean)) {
        var mx = xx(stats.mean);
        el('line', { x1: mx, x2: mx, y1: 0, y2: H - 22, stroke: C.accentHover, 'stroke-width': 1.2 }, g);
        haloText({ 'class': 'axis-text', x: mx, y: 10, 'text-anchor': 'middle' },
          '均值 ' + (stats.mean * 100).toFixed(2) + '%', g);
      }
    }

    wrap.addEventListener('pointerleave', function () { tooltip.hide(); });
    render();
    observeResize(wrap, render);
  }

  /* Per-stock PnL — diverging horizontal bars */
  function stockPnlChart(host, rows) {
    if (!rows || !rows.length) { div('noscript-note', host, '无配对交易'); return; }
    var wrap = div('chart-wrap', host);
    wrap.setAttribute('role', 'img');
    wrap.setAttribute('aria-label', '个股盈亏条形图');
    var rowH = 24, padL = 76, padR = 84;
    var H = rows.length * rowH + 26;
    var svg = el('svg', {}, wrap);
    var tooltip = makeTooltip(wrap);

    function render() {
      var W = wrap.clientWidth || 500;
      svg.setAttribute('width', W); svg.setAttribute('height', H);
      while (svg.firstChild) svg.removeChild(svg.firstChild);
      var g = el('g', {}, svg);

      var mx = 0;
      rows.forEach(function (r) { mx = Math.max(mx, Math.abs(r.pnl)); });
      if (mx <= 0) return;
      var plotW = W - padL - padR;
      /* center zero if both signs present; else start at zero edge */
      var hasNeg = rows.some(function (r) { return r.pnl < 0; });
      var hasPos = rows.some(function (r) { return r.pnl > 0; });
      var cx, scale;
      if (hasNeg && hasPos) { cx = padL + plotW / 2; scale = (plotW / 2) / mx; }
      else if (hasNeg) { cx = padL + plotW; scale = plotW / mx; }
      else { cx = padL; scale = plotW / mx; }

      el('line', { 'class': 'zero-line', x1: cx, x2: cx, y1: 0, y2: H - 22 }, g);

      rows.forEach(function (r, i) {
        var y = i * rowH + 3;
        var w = Math.abs(r.pnl) * scale;
        var x = r.pnl >= 0 ? cx : cx - w;
        var name = el('text', { 'class': 'axis-text', x: padL - 8, y: y + rowH / 2 + 3, 'text-anchor': 'end' }, g);
        name.textContent = r.sec;
        var bar = el('rect', { x: x, y: y, width: Math.max(1, w), height: rowH - 8, fill: r.pnl >= 0 ? C.up : C.down, rx: 2, opacity: 0.88 }, g);
        var val = el('text', {
          'class': 'axis-text', y: y + rowH / 2 + 3,
          x: r.pnl >= 0 ? x + w + 6 : x - 6,
          'text-anchor': r.pnl >= 0 ? 'start' : 'end'
        }, g);
        val.textContent = fmtMoney(r.pnl);
        bar.addEventListener('pointermove', function (e) {
          var rc = wrap.getBoundingClientRect();
          tooltip.show(e.clientX - rc.left, e.clientY - rc.top,
            '<div class="tt-title">' + r.sec + '</div>' +
            '<div class="tt-row"><span class="tt-name">净盈亏</span><span class="tt-value ' + clsDelta(r.pnl) + '">' + fmtMoney(r.pnl) + '</span></div>');
        });
        bar.addEventListener('pointerleave', function () { tooltip.hide(); });
      });
    }

    wrap.addEventListener('pointerleave', function () { tooltip.hide(); });
    render();
    observeResize(wrap, render);
  }

  /* Resize observer helper */
  var _ro = null;
  function observeResize(elm, fn) {
    if (!window.ResizeObserver) return;
    if (!_ro) {
      _ro = new ResizeObserver(function (entries) {
        entries.forEach(function (en) {
          var f = en.target.__rzf;
          if (f) {
            if (en.target.__rzTimer) cancelAnimationFrame(en.target.__rzTimer);
            en.target.__rzTimer = requestAnimationFrame(f);
          }
        });
      });
    }
    elm.__rzf = fn;
    _ro.observe(elm);
  }

  /* ==================================================================== */
  /* Metric glossary drawer                                                */
  /* ==================================================================== */
  var DEFS = {
    ann_ret: { name: '年化收益率', formula: '(1 + 总收益率)^(244/N) − 1', desc: '将回测期间的累计总收益率换算为年化水平，N 为实际回测交易日数。', interp: '>15% 优秀 · >8% 良好 · >0% 正收益 · ≤0% 亏损', ref: 'Geometric Mean Return Annualization', grade: function (v) { return v > 15 ? ['excellent', '优秀 >15%'] : v > 8 ? ['good', '良好 >8%'] : v > 0 ? ['fair', '正收益'] : ['poor', '负收益']; } },
    sharpe: { name: 'Sharpe 比率', formula: '(E[Rp] − rf) / σp × √244', desc: '每单位总风险获得的年化超额收益。无风险利率取 3%，年化天数 244。', interp: '>2.0 优秀 · >1.0 良好 · >0.5 一般 · ≤0.5 较差', ref: 'Sharpe (1966, 1994)', grade: function (v) { return v > 2 ? ['excellent', '优秀 >2.0'] : v > 1 ? ['good', '良好 >1.0'] : v > 0.5 ? ['fair', '一般 >0.5'] : ['poor', '较差']; } },
    sortino: { name: 'Sortino 比率', formula: '(E[Rp] − rf) / σdown × √244', desc: '分母仅计下行波动，更贴近投资者真实承受的风险。', interp: '>2.0 优秀 · >1.0 良好', ref: 'Sortino & Price (1994)', grade: function (v) { return v > 2 ? ['excellent', '优秀 >2.0'] : v > 1 ? ['good', '良好 >1.0'] : v > 0.5 ? ['fair', '一般'] : ['poor', '较差']; } },
    max_dd: { name: '最大回撤', formula: 'max[(峰值 − 谷值) / 峰值]', desc: '净值从历史最高点到随后最低点的最大跌幅。', interp: '<5% 优秀 · <10% 良好 · <20% 可接受 · >20% 偏高', ref: 'Magdon-Ismail & Atiya (2004)', grade: function (v) { var a = Math.abs(v); return a < 5 ? ['excellent', '优秀 <5%'] : a < 10 ? ['good', '良好 <10%'] : a < 20 ? ['fair', '可接受 <20%'] : ['poor', '偏高 >20%']; } },
    win_rate: { name: '交易胜率', formula: '净盈利配对交易数 / 全部配对交易数', desc: 'FIFO 配对的往返交易中，扣除双边费用后净盈亏为正的比例。', interp: '>60% 优秀 · >50% 良好 · 40–50% 一般', ref: 'Van Tharp (1999)', grade: function (v) { return v > 60 ? ['excellent', '优秀 >60%'] : v > 50 ? ['good', '良好 >50%'] : v > 40 ? ['fair', '一般 >40%'] : ['poor', '偏低 <40%']; } },
    daily_win_rate: { name: '日胜率', formula: '盈利交易日数 / 总交易日数', desc: '策略日度收益为正的比例。', interp: '>55% 优秀 · >50% 良好', ref: 'Daily Hit Ratio', grade: function (v) { return v > 55 ? ['excellent', '优秀 >55%'] : v > 50 ? ['good', '良好 >50%'] : ['fair', '一般']; } },
    alpha: { name: 'Alpha', formula: 'α = Rp − [rf + β × (Rm − rf)]', desc: '基于 CAPM 的年化超额收益。正 Alpha 表明策略创造了附加价值。', interp: '>5% 优秀 · >0% 有价值 · <0% 跑输基准', ref: 'Jensen (1968)', grade: function (v) { return v > 5 ? ['excellent', '优秀 >5%'] : v > 0 ? ['good', '正 Alpha'] : v > -5 ? ['fair', '略低'] : ['poor', '负 Alpha']; } },
    beta: { name: 'Beta', formula: 'β = Cov(Rp, Rm) / Var(Rm)', desc: '策略收益对市场基准的敏感度。β=1 同步，>1 放大波动，<1 减弱波动。', interp: '0.3–1.3 为常见可接受区间', ref: 'CAPM: Sharpe (1964)', grade: null },
    excess_return: { name: '超额收益', formula: '策略总收益率 − 基准总收益率', desc: '策略相对基准的绝对超额回报，与基准收益同源同口径。', interp: '>10% 优秀 · >0% 正超额 · <0% 跑输基准', ref: 'Active Return', grade: function (v) { return v > 10 ? ['excellent', '优秀 >10%'] : v > 0 ? ['good', '正超额'] : ['poor', '跑输基准']; } },
    calmar: { name: 'Calmar 比率', formula: '年化收益率 / |最大回撤|', desc: '年化回报相对最大回撤的性价比。', interp: '>1.0 优秀 · >0.5 良好 · <0.3 偏低', ref: 'Young (1991)', grade: function (v) { return v > 1 ? ['excellent', '优秀 >1.0'] : v > 0.5 ? ['good', '良好 >0.5'] : ['fair', '偏低']; } },
    profit_loss_ratio: { name: '盈亏比', formula: '平均单笔盈利 / 平均单笔亏损', desc: '每笔配对交易平均盈利与平均亏损的比率。', interp: '>3:1 优秀 · >2:1 良好 · >1:1 盈利覆盖亏损', ref: 'Van Tharp (1999)', grade: function (v) { return v > 3 ? ['excellent', '优秀 >3:1'] : v > 2 ? ['good', '良好 >2:1'] : v > 1 ? ['fair', '盈利覆盖亏损'] : ['poor', '亏损大于盈利']; } },
    daily_excess: { name: '日均超额收益（年化）', formula: 'mean(策略日收益 − 基准日收益) × 244', desc: '策略每日超额收益的均值乘以年化天数（244）。注意是年化值，非单日值。', interp: '>3% 优秀 · >0% 正超额', ref: 'Daily Active Return', grade: function (v) { return v > 3 ? ['excellent', '优秀 >3%'] : v > 0 ? ['good', '正超额'] : ['poor', '负超额']; } },
    excess_max_dd: { name: '超额收益最大回撤', formula: 'max(超额累积峰值 − 超额累积谷值) / 峰值', desc: '超额收益累积曲线的最大回撤。', interp: '<5% 优秀 · <10% 良好 · >15% 偏高', ref: 'Tracking Error Drawdown', grade: function (v) { var a = Math.abs(v); return a < 5 ? ['excellent', '优秀 <5%'] : a < 10 ? ['good', '良好 <10%'] : a < 15 ? ['fair', '可接受'] : ['poor', '偏高 >15%']; } },
    excess_sharpe: { name: '超额夏普比率', formula: '(E[超额日收益] − rf) / σ(超额日收益) × √244', desc: '以超额日收益为输入的 Sharpe 比率。', interp: '>1.0 优秀 · >0.5 良好', ref: 'Information Ratio variant', grade: function (v) { return v > 1 ? ['excellent', '优秀 >1.0'] : v > 0.5 ? ['good', '良好 >0.5'] : v > 0 ? ['fair', '正值'] : ['poor', '负值']; } },
    info_ratio: { name: '信息比率', formula: 'mean(超额日收益) / std(超额日收益) × √244', desc: '每单位跟踪误差的主动年化收益。', interp: '>0.5 优秀 · >0.3 良好', ref: 'Grinold & Kahn (1999)', grade: function (v) { return v > 0.5 ? ['excellent', '优秀 >0.5'] : v > 0.3 ? ['good', '良好 >0.3'] : v > 0 ? ['fair', '正主动收益'] : ['poor', '负值']; } },
    ann_vol: { name: '策略年化波动率', formula: 'σ(日收益) × √244', desc: '日收益率的年化标准差。', interp: '<10% 低波动 · 10–20% 中等 · >20% 高波动', ref: '', grade: null },
    bm_vol: { name: '基准年化波动率', formula: 'σ(基准日收益) × √244', desc: '基准日收益率的年化标准差，与策略波动率同口径。', interp: '与策略波动率对比', ref: '', grade: null },
    trade_count: { name: '配对交易次数', formula: '', desc: '回测期间完成的 FIFO 配对买卖总次数。样本过少时胜率/盈亏比不具统计意义。', interp: '≥30 次有统计意义', ref: '', grade: null },
    total_return: { name: '总收益率', formula: '(期末总资产 − 初始资金) / 初始资金', desc: '回测区间累计收益率，已扣除佣金与印花税。', interp: '', ref: '', grade: null },
    turnover: { name: '年化换手率', formula: '(买入额 + 卖出额) / 2 / 平均资产 / 年数', desc: '衡量交易频率。换手率过高会放大交易成本对收益的侵蚀。', interp: '', ref: '', grade: null },
    commission: { name: '总交易费用', formula: 'Σ(佣金 + 印花税)', desc: '回测期间支付的全部交易费用。', interp: '', ref: '', grade: null }
  };

  function openDrawer(key, valueText) {
    var def = DEFS[key];
    if (!def) return;
    document.getElementById('drawerTitle').textContent = def.name;
    document.getElementById('drawerValue').textContent = valueText || '';
    var body = '';
    if (def.formula) body += '<div class="drawer-sec"><h5>计算公式</h5><div class="drawer-formula">' + def.formula + '</div></div>';
    if (def.desc) body += '<div class="drawer-sec"><h5>说明</h5><p>' + def.desc + '</p></div>';
    if (def.interp) body += '<div class="drawer-sec"><h5>解读</h5><p>' + def.interp + '</p></div>';
    if (def.grade && valueText) {
      var num = parseFloat(String(valueText).replace(/[%+,]/g, ''));
      if (isFinite(num)) {
        var g = def.grade(num);
        if (g) body += '<div class="drawer-sec"><span class="drawer-grade ' + g[0] + '">' + g[1] + '</span></div>';
      }
    }
    if (def.ref) body += '<div class="drawer-ref">参考：' + def.ref + '</div>';
    document.getElementById('drawerBody').innerHTML = body;
    document.getElementById('metricDrawer').classList.add('open');
    document.getElementById('drawerOverlay').classList.add('open');
  }
  function closeDrawer() {
    document.getElementById('metricDrawer').classList.remove('open');
    document.getElementById('drawerOverlay').classList.remove('open');
  }
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-metric]');
    if (t) { openDrawer(t.dataset.metric, (t.querySelector('.kpi-value, .rm-value') || t).textContent.trim()); }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var t = e.target.closest && e.target.closest('[data-metric]');
    if (t) { e.preventDefault(); openDrawer(t.dataset.metric, (t.querySelector('.kpi-value, .rm-value') || t).textContent.trim()); }
  });
  document.getElementById('drawerClose').addEventListener('click', closeDrawer);
  document.getElementById('drawerOverlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeDrawer(); });

  /* ==================================================================== */
  /* Table sorting                                                         */
  /* ==================================================================== */
  document.querySelectorAll('table.tbl th.sortable').forEach(function (th) {
    th.addEventListener('click', function () {
      var table = th.closest('table');
      var tbody = table.querySelector('tbody');
      var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
      var num = th.dataset.type !== 'str';
      var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
      var dir = th.classList.contains('sorted-asc') ? -1 : 1;
      table.querySelectorAll('th').forEach(function (h) { h.classList.remove('sorted-asc', 'sorted-desc'); });
      th.classList.add(dir === 1 ? 'sorted-asc' : 'sorted-desc');
      rows.sort(function (a, b) {
        var av = a.children[idx] ? a.children[idx].dataset.v || a.children[idx].textContent : '';
        var bv = b.children[b.children.length > idx ? idx : 0] ? b.children[idx].dataset.v || b.children[idx].textContent : '';
        if (num) { av = parseFloat(av); bv = parseFloat(bv); if (!isFinite(av)) av = -Infinity; if (!isFinite(bv)) bv = -Infinity; return (av - bv) * dir; }
        return String(av).localeCompare(String(bv)) * dir;
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });

  /* ==================================================================== */
  /* Scrollspy                                                             */
  /* ==================================================================== */
  (function () {
    var links = document.querySelectorAll('.topbar-nav a');
    if (!links.length || !('IntersectionObserver' in window)) return;
    var map = {};
    links.forEach(function (l) { map[l.getAttribute('href').slice(1)] = l; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          links.forEach(function (l) { l.classList.remove('active'); });
          var l = map[en.target.id];
          if (l) l.classList.add('active');
        }
      });
    }, { rootMargin: '-80px 0px -65% 0px' });
    ['sec-overview', 'sec-returns', 'sec-risk', 'sec-trades', 'sec-method'].forEach(function (id) {
      var s = document.getElementById(id);
      if (s) io.observe(s);
    });
  })();

  /* ==================================================================== */
  /* Boot — main chart tabs                                                */
  /* ==================================================================== */
  var mainHost = document.getElementById('mainChartHost');
  var equityGroup = null, klineGroup = null;
  var currentSymbol = DATA.meta.symbol;

  function mountEquity() {
    mainHost.innerHTML = '';
    var chartDiv = div('', mainHost);
    var sliderDiv = div('', mainHost);
    var presetsHost = document.getElementById('equityPresets');
    if (presetsHost) presetsHost.innerHTML = '';
    equityGroup = buildEquityGroup(chartDiv, sliderDiv, presetsHost);
    observeResize(chartDiv, function () {
      if (equityGroup) { equityGroup.render(); equityGroup.legendRenderer(equityGroup.hoverIndex); }
      if (equityGroup && equityGroup.slider) equityGroup.slider.resize();
    });
  }

  function mountKline(sym) {
    mainHost.innerHTML = '';
    var chartDiv = div('', mainHost);
    var sliderDiv = div('', mainHost);
    klineGroup = buildKlineGroup(chartDiv, sliderDiv, sym);
    if (klineGroup) {
      var t = klineGroup.getToggles();
      document.querySelectorAll('#klineTools [data-ktoggle]').forEach(function (b) {
        b.classList.toggle('active', !!t[b.dataset.ktoggle]);
      });
      observeResize(chartDiv, function () {
        if (klineGroup) { klineGroup.render(); klineGroup.legendRenderer(klineGroup.hoverIndex); }
        if (klineGroup.slider) klineGroup.slider.resize();
      });
    }
    /* tech stats strip */
    var kd = (DATA.kline || {})[sym];
    var tech = kd && kd.tech;
    if (tech && Object.keys(tech).length) {
      var strip = div('tech-strip', mainHost);
      var cells = [
        ['最新', fmtNum(tech.latest_price)],
        ['MA5', fmtNum(tech.ma5)],
        ['MA20', fmtNum(tech.ma20)],
        ['MA60', tech.ma60 == null ? '—' : fmtNum(tech.ma60)],
        ['RSI(14)', tech.rsi14 == null ? '—' : fmtNum(tech.rsi14, 1)],
        ['ATR(14)', tech.atr14 == null ? '—' : fmtNum(tech.atr14, 3)],
        ['量比', tech.vol_ratio == null ? '—' : fmtNum(tech.vol_ratio, 2)],
        ['区间高', fmtNum(tech.period_high)],
        ['区间低', fmtNum(tech.period_low)]
      ];
      cells.forEach(function (c) {
        var s = document.createElement('span');
        s.textContent = c[0];
        var b = document.createElement('b');
        b.textContent = c[1];
        s.appendChild(b);
        strip.appendChild(s);
      });
    }
  }

  /* symbol switcher */
  (function () {
    var host = document.getElementById('symbolSwitch');
    if (!host) return;
    var syms = DATA.meta.symbols || [DATA.meta.symbol];
    syms.forEach(function (s) {
      var b = document.createElement('button');
      b.type = 'button'; b.textContent = s.replace(/\.(XSHG|XSHE)$/, '');
      b.title = s;
      if (s === currentSymbol) b.classList.add('active');
      b.addEventListener('click', function () {
        currentSymbol = s;
        host.querySelectorAll('button').forEach(function (x) { x.classList.toggle('active', x === b); });
        mountKline(s);
      });
      host.appendChild(b);
    });
  })();

  /* kline toggles */
  document.querySelectorAll('#klineTools [data-ktoggle]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (!klineGroup) return;
      var on = !b.classList.contains('active');
      b.classList.toggle('active', on);
      klineGroup.setToggle(b.dataset.ktoggle, on);
    });
  });

  /* main tab switching */
  document.querySelectorAll('[data-maintab]').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('[data-maintab]').forEach(function (x) {
        x.classList.toggle('active', x === b);
        x.setAttribute('aria-selected', x === b ? 'true' : 'false');
      });
      var mode = b.dataset.maintab;
      document.getElementById('equityTools').hidden = mode !== 'equity';
      document.getElementById('klineTools').hidden = mode !== 'kline';
      if (mode === 'equity') mountEquity(); else mountKline(currentSymbol);
    });
  });

  mountEquity();

  /* ==================================================================== */
  /* Boot — secondary charts                                               */
  /* ==================================================================== */
  var distHost = document.getElementById('distChartHost');
  if (distHost && DATA.dist) distChart(distHost, DATA.dist.bins, DATA.dist.stats);

  var annualHost = document.getElementById('annualChartHost');
  if (annualHost) annualChart(annualHost, DATA.annual || []);

  var rollingHost = document.getElementById('rollingChartHost');
  if (rollingHost && DATA.rolling) {
    var rs = DATA.rolling.sharpe || [], rv = DATA.rolling.vol || [];
    var rsDates = rs.map(function (p) { return p.t; }), rsVals = rs.map(function (p) { return p.v; });
    var rvDates = rv.map(function (p) { return p.t; }), rvVals = rv.map(function (p) { return p.v * 100; });
    var row = div('grid-2', rollingHost);
    var h1 = div('', row), h2 = div('', row);
    var lab1 = div('', h1); lab1.className = 'axis-text'; lab1.style.padding = '8px 0 2px 14px'; lab1.textContent = '滚动 Sharpe（目标 1.0）';
    var c1 = div('', h1);
    simpleLineChart(c1, rsDates, [{ name: '滚动 Sharpe', arr: rsVals, color: C.accent, width: 1.4 }],
      { height: 120, ariaLabel: '滚动 60 日 Sharpe', refLines: [{ v: 1.0, label: '1.0' }], fmtV: function (v) { return fmtNum(v, 2); }, fmtY: function (v) { return v.toFixed(1); } });
    var lab2 = div('', h2); lab2.className = 'axis-text'; lab2.style.padding = '8px 0 2px 14px'; lab2.textContent = '滚动年化波动率';
    var c2 = div('', h2);
    simpleLineChart(c2, rvDates, [{ name: '滚动波动率', arr: rvVals, color: C.warn || '#e0a32e', width: 1.4 }],
      { height: 120, ariaLabel: '滚动 60 日年化波动率', fmtV: function (v) { return fmtPct(v, 1); }, fmtY: function (v) { return fmtPct(v, 0); }, includeZero: true });
  }

  var excessHost = document.getElementById('excessChartHost');
  if (excessHost && DATA.excess && DATA.excess.length) {
    divergingAreaChart(excessHost, DATA.dates, DATA.excess, { ariaLabel: '累计超额收益' });
  } else if (excessHost) {
    div('noscript-note', excessHost, '基准数据不可用，无法计算超额收益');
  }

  var allocHost = document.getElementById('allocChartHost');
  if (allocHost && DATA.allocation) {
    allocationChart(allocHost, DATA.dates, DATA.allocation.cash || [], DATA.allocation.invested || []);
  }

  var pnlHost = document.getElementById('stockPnlHost');
  if (pnlHost) stockPnlChart(pnlHost, DATA.per_stock_pnl || []);
})();
