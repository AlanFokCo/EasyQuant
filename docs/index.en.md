---
title: EasyQuant · Event-Driven Backtesting for China A-Shares
template: home.html
hide:
  - toc
  - navigation.path
---

<div class="eql-hero eql-grain" markdown="off">
  <div class="eql-chart" aria-hidden="true"></div>
  <canvas aria-hidden="true"></canvas>
  <span class="eql-chart__tag">Synthetic demo data</span>
  <div class="eql-hero__fade"></div>
  <div class="eql-hero__content eql-wrap">
    <span class="eql-kicker eql-rise" style="animation-delay:.05s">Event-Driven · China A-Share · Open Source</span>
    <h1 class="eql-title eql-rise" style="animation-delay:.18s">A-share backtesting<br>where every cent <em>counts</em>.</h1>
    <p class="eql-sub eql-rise" style="animation-delay:.34s">
      EasyQuant is an event-driven backtesting framework for China's A-share market.
      <strong>Exchange calendar, price-limit enforcement, T+1, fees and slippage</strong> —
      production-grade market semantics in a single <code>pip install</code>.
    </p>
    <div class="eql-cta-row eql-rise" style="animation-delay:.5s">
      <a class="eql-btn eql-btn--primary" href="tutorials/00-getting-started/">Get started in 15 min →</a>
      <a class="eql-btn eql-btn--ghost" href="https://github.com/AlanFokCo/EasyQuant">GitHub ★</a>
    </div>
    <div class="eql-install eql-rise" style="animation-delay:.64s">
      <span class="prompt">$</span><span class="cmd">pip install easyquant-eqlib</span>
      <button class="eql-install__copy" data-copied="copied">copy</button>
    </div>
  </div>
  <div class="eql-scrollhint">Scroll</div>
</div>

<div class="eql-ticker" markdown="off" aria-label="Sample quotes (demo data)">
  <div class="eql-ticker__track">
    <span class="eql-tick"><b>SSE Composite</b> 3,247.86 <span class="up">+0.87%</span></span>
    <span class="eql-tick"><b>SZSE Component</b> 10,562.13 <span class="up">+1.24%</span></span>
    <span class="eql-tick"><b>ChiNext</b> 2,183.45 <span class="down">−0.62%</span></span>
    <span class="eql-tick"><b>CSI 300</b> 3,912.60 <span class="up">+0.45%</span></span>
    <span class="eql-tick"><b>CSI 500</b> 5,834.02 <span class="down">−0.18%</span></span>
    <span class="eql-tick"><b>STAR 50</b> 986.71 <span class="up">+2.03%</span></span>
    <span class="eql-tick"><span class="lbl">Northbound</span><span class="up">+5.82B inflow</span></span>
    <span class="eql-tick"><span class="lbl">Limit up/down</span><span class="up">62</span> / <span class="down">7</span></span>
    <span class="eql-tick"><span class="lbl">Turnover</span><b>984.2B</b></span>
    <span class="eql-tick"><span class="lbl">Demo data · not live</span></span>
  </div>
</div>

<section class="eql-section" markdown="off">
  <div class="eql-wrap">
    <div class="eql-stats eql-reveal">
      <div class="eql-stat"><div class="eql-stat__num" data-eql-count="1400">0<span class="suffix">+</span></div><div class="eql-stat__lbl">unit tests<br>driven by adversarial audits</div></div>
      <div class="eql-stat"><div class="eql-stat__num" data-eql-count="25">0</div><div class="eql-stat__lbl">battle-tested examples<br>from first backtest to portfolios</div></div>
      <div class="eql-stat"><div class="eql-stat__num" data-eql-count="26">0</div><div class="eql-stat__lbl">data APIs with PIT guards<br>no future data in-session</div></div>
      <div class="eql-stat"><div class="eql-stat__num" data-eql-count="244">0<span class="suffix">d</span></div><div class="eql-stat__lbl">annualization basis<br>true A-share trading days</div></div>
    </div>
  </div>
</section>

<section class="eql-section eql-section--alt" markdown="off">
  <div class="eql-wrap">
    <div class="eql-sec-head eql-reveal">
      <div class="eql-sec-tag">Capabilities</div>
      <h2 class="eql-sec-title">One framework, from research to live trading</h2>
    </div>
    <div class="eql-features eql-reveal">
      <div class="eql-feat eql-feat--xl">
        <div class="eql-feat__idx">01</div>
        <div class="eql-feat__icon">⚙</div>
        <h3>Event-Driven Engine</h3>
        <p><code>initialize</code> → <code>run_daily</code> → <code>handle_data</code>, compatible with the JoinQuant / Zipline mental model. Signals on day T fill at day T+1 open — no look-ahead, by construction.</p>
        <a class="eql-feat__link" href="explanation/backtest-model/">Execution model →</a>
      </div>
      <div class="eql-feat">
        <div class="eql-feat__idx">02</div>
        <div class="eql-feat__icon">▤</div>
        <h3>Full A-Share Data</h3>
        <p>Daily / minute / tick bars, fundamentals, money flow, northbound capital, limit-up/down stats. Local cache with resumable downloads for reproducible offline research.</p>
        <a class="eql-feat__link" href="reference/api-data/">Data APIs →</a>
      </div>
      <div class="eql-feat">
        <div class="eql-feat__idx">03</div>
        <div class="eql-feat__icon">∑</div>
        <h3>Risk & Attribution</h3>
        <p>Sharpe / Sortino / Max Drawdown / Alpha·Beta, and a true single-period BHB Brinson attribution — allocation + selection + interaction, mathematically closed.</p>
        <a class="eql-feat__link" href="reference/api-analysis/">Analysis APIs →</a>
      </div>
      <div class="eql-feat">
        <div class="eql-feat__idx">04</div>
        <div class="eql-feat__icon">⛨</div>
        <h3>Portfolio Risk</h3>
        <p>VaR, strategy correlation, concentration, and a kill switch.</p>
        <a class="eql-feat__link" href="how-to/portfolio-risk/">Risk guides →</a>
      </div>
      <div class="eql-feat">
        <div class="eql-feat__idx">05</div>
        <div class="eql-feat__icon">◉</div>
        <h3>Paper Trading + Alerts</h3>
        <p>Live-data paper trading with session gating, DingTalk / Feishu push.</p>
        <a class="eql-feat__link" href="how-to/paper-trade/">Paper trading →</a>
      </div>
      <div class="eql-feat eql-feat--full">
        <div class="eql-feat__idx">06</div>
        <div class="eql-feat__icon">⇄</div>
        <div><h3>PTrade · QMT Export</h3>
        <p>One-click export to broker platforms — research to trading, seamless.</p>
        <a class="eql-feat__link" href="how-to/export-ptrade/">Export guide →</a></div>
      </div>
    </div>
  </div>
</section>

<section class="eql-section" markdown="off">
  <div class="eql-wrap">
    <div class="eql-rigor">
      <div>
        <div class="eql-sec-head eql-reveal">
          <div class="eql-sec-tag">Rigor</div>
          <h2 class="eql-sec-title">Four lines of defense,<br>so results survive review</h2>
          <p class="eql-sec-sub">The hard rules of the A-share market — exchange calendar, price limits, T+1, fees — are default behaviors in EasyQuant, not options.</p>
        </div>
        <div class="eql-rigor__list eql-reveal">
          <div class="eql-rigor__item">
            <span class="eql-rigor__no">Ⅰ</span>
            <div class="eql-rigor__body">
              <h4>Price limits enforced by default</h4>
              <p><code>check_price_limit=True</code> on by default; board- and date-aware limit table (ChiNext 20% since 2020-08-24), 5% ST channel. One-way limit boards can't be bought or sold into.</p>
            </div>
          </div>
          <div class="eql-rigor__item">
            <span class="eql-rigor__no">Ⅱ</span>
            <div class="eql-rigor__body">
              <h4>PIT data contract</h4>
              <p>26 data APIs truncate to T-1 or warn inside backtest sessions; <code>avoid_future_data</code> strict mode raises.</p>
            </div>
          </div>
          <div class="eql-rigor__item">
            <span class="eql-rigor__no">Ⅲ</span>
            <div class="eql-rigor__body">
              <h4>Exchange-authoritative calendar</h4>
              <p>Suspension-day orders cancelled same-day with recorded reasons; delisted positions force-liquidated after prolonged absence of bars. Backtest windows are never silently truncated.</p>
            </div>
          </div>
          <div class="eql-rigor__item">
            <span class="eql-rigor__no">Ⅳ</span>
            <div class="eql-rigor__body">
              <h4>Cost-honest metrics</h4>
              <p>Win rate and profit/loss ratio include two-sided commission and stamp duty; missing benchmarks render <code>N/A</code> instead of silent numbers.</p>
            </div>
          </div>
        </div>
      </div>
      <div class="eql-reveal" data-eql-delay="120">
        <div class="eql-term">
          <div class="eql-term__bar"><span class="eql-term__dot"></span><span class="eql-term__dot"></span><span class="eql-term__dot"></span><span class="eql-term__title">strategy.py — eqlib</span></div>
          <div class="eql-term__body" data-eql-type markdown="off">from eqlib import *

def initialize(context):
    g.security = '601390'          # China Railway Group
    set_benchmark('000300.XSHG')   # CSI 300
    run_daily(market_open, time='every_bar')

def market_open(context):
    hist = attribute_history(g.security, 20, '1d', ['close'])
    ma20 = hist['close'].mean()
    price = hist['close'].iloc[-1]
    if price > ma20 * 1.02:        # breakout: full position
        order_value(g.security, context.portfolio.available_cash)
    elif price < ma20 * 0.98:      # breakdown: exit
        order_target(g.security, 0)

result = run_strategy(initialize,
    start_date='2024-01-01', end_date='2024-12-31',
    starting_cash=100000, securities=['601390'])

# ✓ Fills respect price limits / T+1 / fees, no look-ahead
# Sample output (synthetic data, not a promise of returns):
# Total return +21.88% · Sharpe 0.33 · Max drawdown -9.4%</div>
        </div>
      </div>
    </div>
  </div>
</section>

<section class="eql-section eql-section--alt" markdown="off">
  <div class="eql-wrap">
    <div class="eql-sec-head eql-reveal">
      <div class="eql-sec-tag">Reports</div>
      <h2 class="eql-sec-title">Every backtest ships a review-ready report</h2>
      <p class="eql-sec-sub">Equity curve, drawdown, monthly returns, per-trade ledger, attribution — in HTML / Markdown / JSON / PNG, ready for your research review.</p>
    </div>
    <div class="eql-gallery eql-reveal">
      <a class="eql-shot" href="assets/tutorials/example_report_html_macd_volume.png" target="_blank">
        <img src="assets/tutorials/example_report_html_macd_volume.png" alt="MACD trend + volume strategy report" loading="lazy">
        <span class="eql-shot__cap">MACD trend + volume<small>Signals and equity curve</small></span>
      </a>
      <a class="eql-shot" href="assets/tutorials/example_report_html_bollinger.png" target="_blank">
        <img src="assets/tutorials/example_report_html_bollinger.png" alt="Bollinger mean-reversion strategy report" loading="lazy">
        <span class="eql-shot__cap">Bollinger mean reversion<small>Per-trade ledger and drawdown</small></span>
      </a>
      <a class="eql-shot" href="assets/tutorials/example_report_html_portfolio.png" target="_blank">
        <img src="assets/tutorials/example_report_html_portfolio.png" alt="Portfolio strategy backtest report" loading="lazy">
        <span class="eql-shot__cap">Portfolio strategy<small>Multi-stock scoring and risk attribution</small></span>
      </a>
    </div>
    <p style="color:var(--eql-faint);font-size:0.75rem;margin-top:1.2rem;font-family:var(--eql-mono)">Results vary with market conditions. Samples shown for illustration only.</p>
  </div>
</section>

<section class="eql-cta eql-grain" markdown="off">
  <div class="eql-wrap eql-reveal">
    <h2 class="eql-cta__title">From install to your first backtest report<br>in about <em>15 minutes</em>.</h2>
    <p class="eql-sub" style="text-align:center">From install to your first trustworthy backtest report — tutorials, examples and API references are all ready.</p>
    <div class="eql-cta-row" style="justify-content:center">
      <a class="eql-btn eql-btn--primary" href="tutorials/00-getting-started/">Start the tutorial →</a>
      <a class="eql-btn eql-btn--ghost" href="examples/">Browse 25 examples</a>
    </div>
  </div>
</section>

<div class="eql-wrap" markdown="off" style="padding-bottom:2.5rem">
  <p style="color:var(--eql-faint);font-size:0.75rem;text-align:center;font-family:var(--eql-mono)">For research and education only. Not investment advice. · 仅供学习研究，不构成投资建议</p>
</div>
