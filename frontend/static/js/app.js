const { useEffect, useMemo, useRef, useState } = React;

const API_BASE = "";

function formatINR(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function formatDateLabel(dateString) {
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return dateString;
  const hasIntradayTime = date.getHours() !== 0 || date.getMinutes() !== 0 || date.getSeconds() !== 0;
  if (hasIntradayTime) {
    return date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
  }
  return date.toLocaleDateString("en-IN", { month: "short", day: "numeric" });
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toFixed(2)}%`;
}

function useDebouncedValue(value, delay = 200) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

function PriceChart({ series, symbol, days, prediction, viewMode, sessionDate }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !series || series.length === 0) return;

    const closePrices = series.map((d) => Number(d.close_price));
    const ma7 = series.map((d) => (d.moving_avg_7 != null ? Number(d.moving_avg_7) : null));
    const forecastRows = viewMode === "range" ? prediction?.predictions || [] : [];
    const forecast = forecastRows.map((item) => Number(item.predicted_close));
    const upperBand = forecastRows.map((item) => Number(item.upper_95));
    const lowerBand = forecastRows.map((item) => Number(item.lower_95));
    const forecastHorizon = forecastRows.length;

    const labels = [
      ...series.map((d) => formatDateLabel(d.date)),
      ...forecastRows.map((item, idx) => item.label || `P+${idx + 1}`),
    ];

    const closeSeriesData = [...closePrices, ...Array.from({ length: forecastHorizon }, () => null)];
    const ma7SeriesData = [...ma7, ...Array.from({ length: forecastHorizon }, () => null)];
    const predictionData = [
      ...Array.from({ length: closePrices.length - 1 }, () => null),
      closePrices[closePrices.length - 1],
      ...forecast,
    ];
    const upperBandData = [
      ...Array.from({ length: closePrices.length - 1 }, () => null),
      closePrices[closePrices.length - 1],
      ...upperBand,
    ];
    const lowerBandData = [
      ...Array.from({ length: closePrices.length - 1 }, () => null),
      closePrices[closePrices.length - 1],
      ...lowerBand,
    ];

    const start = closePrices[0];
    const end = closePrices[closePrices.length - 1];
    const gain = end >= start;

    if (chartRef.current) {
      chartRef.current.destroy();
    }

    const datasets = [
      {
        label: `${symbol} Close`,
        data: closeSeriesData,
        borderColor: gain ? "#16a34a" : "#dc2626",
        backgroundColor: gain ? "rgba(22,163,74,0.12)" : "rgba(220,38,38,0.12)",
        borderWidth: 2.5,
        tension: 0.35,
        fill: true,
        pointRadius: 0,
        pointHoverRadius: 5,
      },
    ];

    if (ma7.some((value) => value != null)) {
      datasets.push({
        label: "MA 7",
        data: ma7SeriesData,
        borderColor: "#f59e0b",
        borderWidth: 1.5,
        borderDash: [6, 4],
        tension: 0.35,
        fill: false,
        pointRadius: 0,
      });
    }

    if (forecastHorizon > 0) {
      datasets.push(
        {
          label: prediction?.metadata?.model_type ? `Prediction (${prediction.metadata.model_type})` : "Prediction",
          data: predictionData,
          borderColor: "#2563eb",
          borderWidth: 2,
          borderDash: [4, 4],
          tension: 0.2,
          fill: false,
          pointRadius: 0,
          pointHoverRadius: 4,
        },
        {
          label: "Upper 95%",
          data: upperBandData,
          borderColor: "rgba(37, 99, 235, 0.5)",
          borderWidth: 1.5,
          borderDash: [2, 4],
          tension: 0.2,
          fill: false,
          pointRadius: 0,
        },
        {
          label: "Lower 95%",
          data: lowerBandData,
          borderColor: "rgba(37, 99, 235, 0.5)",
          borderWidth: 1.5,
          borderDash: [2, 4],
          tension: 0.2,
          fill: false,
          pointRadius: 0,
        }
      );
    }

    chartRef.current = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        plugins: {
          legend: {
            labels: {
              color: "#334155",
              usePointStyle: true,
              boxWidth: 8,
            },
          },
          tooltip: {
            callbacks: {
              label(context) {
                return `${context.dataset.label}: ${formatINR(context.parsed.y)}`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: "rgba(148,163,184,0.16)" },
            ticks: { color: "#64748b", maxTicksLimit: 8 },
            title: {
              display: true,
              text: viewMode === "session" ? `Session: ${sessionDate}` : `Last ${days} days`,
              color: "#64748b",
            },
          },
          y: {
            grid: { color: "rgba(148,163,184,0.16)" },
            ticks: {
              color: "#64748b",
              callback(value) {
                return formatINR(value);
              },
            },
          },
        },
      },
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [series, symbol, days, prediction, viewMode, sessionDate]);

  return (
    <div className="chart-card">
      <div className="section-title-row">
        <h3>Price Trend</h3>
        <span className="muted-chip">
          {prediction?.metadata?.pipeline_version ? `Model ${prediction.metadata.pipeline_version}` : "Interactive"}
        </span>
      </div>
      <div className="chart-wrap">
        <canvas ref={canvasRef}></canvas>
      </div>
      {prediction?.metadata?.metrics && (
        <div className="model-metrics">
          <div className="model-metric-item">
            <span>MAE</span>
            <strong>{Number(prediction.metadata.metrics.mae || 0).toFixed(2)}</strong>
          </div>
          <div className="model-metric-item">
            <span>RMSE</span>
            <strong>{Number(prediction.metadata.metrics.rmse || 0).toFixed(2)}</strong>
          </div>
          <div className="model-metric-item">
            <span>Train/Test</span>
            <strong>{`${prediction.metadata.training_rows || 0}/${prediction.metadata.test_rows || 0}`}</strong>
          </div>
          <div className="model-metric-item">
            <span>Model Cache</span>
            <strong>{prediction.metadata.cache_hit ? "Hit" : "Miss"}</strong>
          </div>
        </div>
      )}
    </div>
  );
}

function StockAnalysisSkeleton() {
  return (
    <div className="stock-skeleton" aria-label="Loading stock analysis" aria-busy="true">
      <div className="skeleton-header">
        <div className="skeleton-line skeleton-line-lg"></div>
        <div className="skeleton-chip"></div>
      </div>

      <div className="skeleton-grid metrics-grid">
        <div className="skeleton-card"></div>
        <div className="skeleton-card"></div>
        <div className="skeleton-card"></div>
        <div className="skeleton-card"></div>
        <div className="skeleton-card"></div>
      </div>

      <div className="skeleton-filter-row filters">
        <div className="skeleton-button"></div>
        <div className="skeleton-button"></div>
        <div className="skeleton-button"></div>
      </div>

      <div className="chart-card skeleton-chart-card">
        <div className="section-title-row">
          <div className="skeleton-line skeleton-line-md"></div>
          <div className="skeleton-chip"></div>
        </div>
        <div className="chart-wrap skeleton-chart"></div>
        <div className="skeleton-subgrid analysis-grid">
          <div className="skeleton-panel"></div>
          <div className="skeleton-panel"></div>
          <div className="skeleton-panel"></div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [companies, setCompanies] = useState([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [companiesError, setCompaniesError] = useState("");

  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 180);

  const [selected, setSelected] = useState(null);
  const [days, setDays] = useState(30);
  const [viewMode, setViewMode] = useState("range");
  const [sessionDate, setSessionDate] = useState(() => {
    const date = new Date();
    date.setDate(date.getDate() - 1);
    return date.toISOString().slice(0, 10);
  });

  const [series, setSeries] = useState([]);
  const [summary, setSummary] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [stockLoading, setStockLoading] = useState(false);
  const [stockError, setStockError] = useState("");
  const [sessionStatus, setSessionStatus] = useState(null);
  const [comparisonSymbol, setComparisonSymbol] = useState("");
  const [correlation, setCorrelation] = useState(null);
  const [correlationLoading, setCorrelationLoading] = useState(false);
  const [correlationError, setCorrelationError] = useState("");

  const [analytics, setAnalytics] = useState({ gainers: [], losers: [] });
  const [dataSourceRemark, setDataSourceRemark] = useState("");

  const filteredCompanies = useMemo(() => {
    const term = debouncedSearch.trim().toLowerCase();
    if (!term) return companies;
    return companies.filter((c) => {
      const symbol = (c.symbol || "").toLowerCase();
      const name = (c.name || "").toLowerCase();
      return symbol.includes(term) || name.includes(term);
    });
  }, [companies, debouncedSearch]);

  useEffect(() => {
    let mounted = true;

    async function loadCompanies() {
      setCompaniesLoading(true);
      setCompaniesError("");
      try {
        const res = await fetch(`${API_BASE}/companies`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!mounted) return;
        setCompanies(data || []);
      } catch (err) {
        if (!mounted) return;
        setCompaniesError("Unable to load companies. Please check if server is running.");
      } finally {
        if (mounted) setCompaniesLoading(false);
      }
    }

    async function loadAnalytics() {
      try {
        const [g, l] = await Promise.all([
          fetch(`${API_BASE}/data/analytics/top-gainers?days=1&limit=5`).then((r) => (r.ok ? r.json() : [])),
          fetch(`${API_BASE}/data/analytics/top-losers?days=1&limit=5`).then((r) => (r.ok ? r.json() : [])),
        ]);
        if (!mounted) return;
        setAnalytics({ gainers: g || [], losers: l || [] });
      } catch (err) {
        if (!mounted) return;
        setAnalytics({ gainers: [], losers: [] });
      }
    }

    loadCompanies();
    loadAnalytics();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selected?.symbol) return;

    let mounted = true;

    async function loadSelectedStock() {
      setStockLoading(true);
      setStockError("");
      if (viewMode !== "session") {
        setSessionStatus(null);
      }
      try {
        const symbol = selected.symbol;
        const trainingDays = Math.max(days, 180);
        const seriesUrl =
          viewMode === "session"
            ? `${API_BASE}/data/session/${symbol}?trade_date=${encodeURIComponent(sessionDate)}&interval=5min`
            : `${API_BASE}/data/${symbol}?days=${days}`;

        const [seriesRes, summaryRes, providerRes] = await Promise.all([
          fetch(seriesUrl),
          fetch(`${API_BASE}/data/summary/${symbol}`),
          fetch(`${API_BASE}/data/provider-status/${symbol}`).catch(() => null),
        ]);

        if (!seriesRes.ok || !summaryRes.ok) {
          const seriesBody = await seriesRes.json().catch(() => null);
          const summaryBody = await summaryRes.json().catch(() => null);
          const serverDetail = seriesBody?.detail || summaryBody?.detail;
          if (seriesRes.status === 404 || summaryRes.status === 404) {
            throw new Error(serverDetail || "No stock data found. Run populate_database.py to load historical records.");
          }
          throw new Error(serverDetail || "Failed to fetch stock data");
        }

        const [seriesData, summaryData] = await Promise.all([seriesRes.json(), summaryRes.json()]);

        const sessionSource = seriesRes.headers.get("x-session-source");
        const sessionMessage = seriesRes.headers.get("x-session-message");

        let predictionData = null;
        if (viewMode === "range") {
          try {
            const predictionRes = await fetch(
              `${API_BASE}/data/prediction/${symbol}?history_days=${trainingDays}&horizon=7`
            );
            if (predictionRes.ok) {
              predictionData = await predictionRes.json();
            }
          } catch (predictionErr) {
            predictionData = null;
          }
        }

        if (!mounted) return;
        setSeries(seriesData || []);
        setSummary(summaryData || null);
        setPrediction(predictionData || null);
        if (viewMode === "session") {
          setSessionStatus({
            source: sessionSource || "unknown",
            message: sessionMessage || "Session data loaded.",
          });
          const fallback = (sessionSource || "").toLowerCase() === "fallback_daily";
          setDataSourceRemark(
            fallback
              ? `Data source: Fallback daily data. ${sessionMessage || "Using fallback session data."}`
              : "Data source: Alpha Vantage intraday API."
          );
        } else {
          const providerData = providerRes && providerRes.ok ? await providerRes.json() : null;
          const providerMessage = (providerData?.message || "").toLowerCase();
          if (providerData?.is_live) {
            setDataSourceRemark("Data source: Alpha Vantage daily API.");
          } else if (providerMessage.includes("rate limit") || providerMessage.includes("quota")) {
            setDataSourceRemark("Data source: NSELib fallback (Alpha Vantage quota limit reached).");
          } else if (providerMessage.includes("not configured")) {
            setDataSourceRemark("Data source: NSELib fallback (Alpha Vantage API key not configured).");
          } else {
            setDataSourceRemark("Data source: Fallback provider (NSELib/yfinance/stored data).");
          }
        }
      } catch (err) {
        if (!mounted) return;
        setSeries([]);
        setSummary(null);
        setPrediction(null);
        setSessionStatus(null);
        setDataSourceRemark("");
        setStockError(err.message || "Could not load selected stock data.");
      } finally {
        if (mounted) setStockLoading(false);
      }
    }

    loadSelectedStock();

    return () => {
      mounted = false;
    };
  }, [selected, days, viewMode, sessionDate]);

  useEffect(() => {
    if (!selected?.symbol || companies.length === 0) return;
    const fallback = companies.find((c) => c.symbol !== selected.symbol);
    if (!fallback) {
      setComparisonSymbol("");
      return;
    }
    if (!comparisonSymbol || comparisonSymbol === selected.symbol) {
      setComparisonSymbol(fallback.symbol);
    }
  }, [selected, companies, comparisonSymbol]);

  useEffect(() => {
    if (viewMode === "session") {
      setCorrelation(null);
      setCorrelationError("");
      return;
    }

    if (days < 30) {
      setCorrelation(null);
      setCorrelationError("Correlation is available for 30+ day windows.");
      return;
    }

    if (!selected?.symbol || !comparisonSymbol || selected.symbol === comparisonSymbol) {
      setCorrelation(null);
      return;
    }

    let mounted = true;

    async function loadCorrelation() {
      setCorrelationLoading(true);
      setCorrelationError("");
      try {
        const url = `${API_BASE}/data/analytics/correlation?symbol1=${encodeURIComponent(selected.symbol)}&symbol2=${encodeURIComponent(comparisonSymbol)}&days=${days}`;
        const res = await fetch(url);
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        if (!mounted) return;
        setCorrelation(data);
      } catch (err) {
        if (!mounted) return;
        setCorrelation(null);
        setCorrelationError(err.message || "Unable to compute correlation.");
      } finally {
        if (mounted) setCorrelationLoading(false);
      }
    }

    loadCorrelation();

    return () => {
      mounted = false;
    };
  }, [selected, comparisonSymbol, days, viewMode]);

  const trendUp = useMemo(() => {
    if (!series || series.length < 2) return true;
    const first = Number(series[0].close_price);
    const last = Number(series[series.length - 1].close_price);
    return last >= first;
  }, [series]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>Stock Intelligence Dashboard</h1>
          <p>Fast insights on selected stocks with seamless analysis views.</p>
          {dataSourceRemark && <p className="muted-subtext">{dataSourceRemark}</p>}
        </div>
        <div className="topbar-tag">Data Feed</div>
      </header>

      <main className="layout">
        <aside className="sidebar">
          <div className="search-wrap">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search company or symbol"
            />
          </div>

          <div className="company-list" role="listbox" aria-label="Companies">
            {companiesLoading && <div className="state-msg">Loading companies...</div>}
            {companiesError && <div className="state-msg error">{companiesError}</div>}
            {!companiesLoading && !companiesError && filteredCompanies.length === 0 && (
              <div className="state-msg">No companies found.</div>
            )}

            {!companiesLoading && !companiesError && filteredCompanies.map((company) => {
              const active = selected?.symbol === company.symbol;
              return (
                <button
                  key={company.symbol}
                  className={`company-item ${active ? "active" : ""}`}
                  onClick={() => {
                    setSelected(company);
                    setDays(30);
                    setViewMode("range");
                  }}
                >
                  <div className="company-top">
                    <strong>{company.symbol}</strong>
                    <span className="sector-pill">{company.sector || "Stock"}</span>
                  </div>
                  <div className="company-name">{company.name || "Unknown Company"}</div>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="content">
          {!selected && (
            <div className="hero-empty dashboard-intro">
              <div className="intro-kicker">Welcome</div>
              <h2>Explore stock trends, summaries, and predictions</h2>
              <p>
                Use the list on the left to open any stock and see its price chart, key metrics,
                correlation checks, and forecast view. Nothing is preselected, so the dashboard
                starts as a clean overview.
              </p>
              <div className="intro-points">
                <div>
                  <strong>Track performance</strong>
                  <span>Review daily movement, volatility, and 52-week levels.</span>
                </div>
                <div>
                  <strong>Compare stocks</strong>
                  <span>Switch between symbols to inspect correlation and relative behavior.</span>
                </div>
                <div>
                  <strong>See forecasts</strong>
                  <span>Open a stock to load prediction visuals and model details.</span>
                </div>
              </div>
            </div>
          )}

          {selected && (
            <>
              <div className="stock-head">
                <div>
                  <h2>{selected.symbol}</h2>
                  <p>{selected.name || "Selected stock"}</p>
                </div>
                <span className={`trend-dot ${trendUp ? "up" : "down"}`}>
                  {trendUp ? "Uptrend" : "Downtrend"}
                </span>
              </div>

              <div className="metrics-grid">
                <article className="metric">
                  <span>Current Price</span>
                  <strong>{formatINR(summary?.current_price)}</strong>
                </article>
                <article className="metric">
                  <span>52-Week High</span>
                  <strong>{formatINR(summary?.week_52_high)}</strong>
                </article>
                <article className="metric">
                  <span>52-Week Low</span>
                  <strong>{formatINR(summary?.week_52_low)}</strong>
                </article>
                <article className="metric">
                  <span>Average Close</span>
                  <strong>{formatINR(summary?.avg_close)}</strong>
                </article>
                <article className="metric">
                  <span>Volatility (30D, Ann.)</span>
                  <strong>{formatPercent(summary?.volatility_30d)}</strong>
                  <small>{summary?.volatility_band || "-"}</small>
                </article>
              </div>

              <div className="filters">
                <button
                  onClick={() => setViewMode("session")}
                  className={viewMode === "session" ? "active" : ""}
                >
                  Session Day
                </button>
                {viewMode === "session" && (
                  <input
                    type="date"
                    value={sessionDate}
                    max={new Date().toISOString().slice(0, 10)}
                    onChange={(e) => setSessionDate(e.target.value)}
                  />
                )}
                {[30, 90].map((d) => (
                  <button
                    key={d}
                    onClick={() => {
                      setViewMode("range");
                      setDays(d);
                    }}
                    className={viewMode === "range" && days === d ? "active" : ""}
                  >
                    {`Last ${d} Days`}
                  </button>
                ))}
              </div>

              {viewMode === "session" && sessionStatus?.message && (
                <div className={`state-msg ${sessionStatus.source === "fallback_daily" ? "warning" : ""}`}>
                  {sessionStatus.source === "fallback_daily"
                    ? "Session source: Fallback. "
                    : "Session source: Live API. "}
                  {sessionStatus.message}
                </div>
              )}

              {stockLoading && <StockAnalysisSkeleton />}
              {stockError && <div className="state-msg error">{stockError}</div>}
              {!stockLoading && !stockError && series.length > 0 && (
                <PriceChart
                  series={series}
                  symbol={selected.symbol}
                  days={days}
                  prediction={prediction}
                  viewMode={viewMode}
                  sessionDate={sessionDate}
                />
              )}
              {!stockLoading && !stockError && series.length === 0 && (
                <div className="state-msg">No chart data available for this stock.</div>
              )}

              <div className="analysis-grid">
                <section className="analysis-card">
                  <div className="section-title-row">
                    <h3>Correlation</h3>
                    <span className="muted-chip">{days}d</span>
                  </div>
                  <label className="inline-label" htmlFor="correlation-symbol-select">Compare with</label>
                  <select
                    id="correlation-symbol-select"
                    className="analysis-select"
                    value={comparisonSymbol}
                    onChange={(e) => setComparisonSymbol(e.target.value)}
                  >
                    {companies
                      .filter((c) => c.symbol !== selected.symbol)
                      .map((c) => (
                        <option key={c.symbol} value={c.symbol}>
                          {c.symbol}
                        </option>
                      ))}
                  </select>

                  {correlationLoading && <div className="state-msg">Calculating correlation...</div>}
                  {correlationError && <div className="state-msg error">{correlationError}</div>}
                  {!correlationLoading && !correlationError && correlation && (
                    <div className="row-item correlation-row">
                      <span>
                        {correlation.symbol1} vs {correlation.symbol2}
                      </span>
                      <strong className={Number(correlation.correlation) >= 0 ? "up" : "down"}>
                        {Number(correlation.correlation).toFixed(2)}
                      </strong>
                      <div className="correlation-gauge" aria-label="Correlation gauge">
                        <div className="correlation-gauge-track"></div>
                        <div
                          className="correlation-gauge-marker"
                          style={{ left: `${((Number(correlation.correlation) + 1) / 2) * 100}%` }}
                        ></div>
                        <div className="correlation-gauge-labels">
                          <span>-1</span>
                          <span>0</span>
                          <span>+1</span>
                        </div>
                      </div>
                      <span className="muted-subtext">{correlation.relationship}</span>
                    </div>
                  )}
                </section>

                <section className="analysis-card">
                  <div className="section-title-row">
                    <h3>Top Gainers</h3>
                    <span className="muted-chip positive">Today</span>
                  </div>
                  {analytics.gainers.length === 0 && <div className="state-msg">No gainers available.</div>}
                  {analytics.gainers.map((item) => (
                    <div key={`g-${item.symbol}`} className="row-item">
                      <span>{item.symbol}</span>
                      <strong className="up">+{item.change_percent}%</strong>
                    </div>
                  ))}
                </section>

                <section className="analysis-card">
                  <div className="section-title-row">
                    <h3>Top Losers</h3>
                    <span className="muted-chip negative">Today</span>
                  </div>
                  {analytics.losers.length === 0 && <div className="state-msg">No losers available.</div>}
                  {analytics.losers.map((item) => (
                    <div key={`l-${item.symbol}`} className="row-item">
                      <span>{item.symbol}</span>
                      <strong className="down">{item.change_percent}%</strong>
                    </div>
                  ))}
                </section>
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
