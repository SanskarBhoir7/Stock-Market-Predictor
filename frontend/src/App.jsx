import React, { useContext, useEffect, useRef, useState } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom';
import {
  Activity,
  BarChart2,
  Globe2,
  LogOut,
  Newspaper,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Wallet,
} from 'lucide-react';

import { CandlestickChart } from './components/CandlestickChart';
import { AuthContext } from './context/AuthContext.js';
import { AuthProvider } from './context/AuthContext.jsx';
import Auth from './pages/Auth';
import { marketService } from './services/api';

const TIMEFRAMES = [
  { id: '1d', label: 'Daily', period: '1y' },
  { id: '1h', label: 'Hourly', period: '3mo' },
  { id: '5m', label: '5 Min', period: '1mo' },
];

const AGENT_META = {
  macro_geopolitics: { label: 'Macro Geopolitics', icon: Globe2 },
  commodities_fx: { label: 'Commodities and FX', icon: Wallet },
  news_sentiment: { label: 'News Sentiment', icon: Newspaper },
  technical_flow: { label: 'Technical Flow', icon: TrendingUp },
  risk_manager: { label: 'Decision Engine', icon: ShieldCheck },
};

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useContext(AuthContext);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-100 tracking-[0.3em] uppercase">
        Loading market workspace
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/auth" />;
  }

  return children;
};

const decisionTheme = (decision) => {
  if (decision === 'BUY') {
    return {
      badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/30',
      accent: 'text-emerald-300',
    };
  }
  if (decision === 'NO_BUY') {
    return {
      badge: 'bg-rose-500/15 text-rose-300 border-rose-400/30',
      accent: 'text-rose-300',
    };
  }
  return {
    badge: 'bg-amber-500/15 text-amber-200 border-amber-400/30',
    accent: 'text-amber-200',
  };
};

const voteTone = (value) => {
  if (value === 'Bullish' || value === 'Risk-On' || value === 'BUY' || value === 'UP') {
    return 'text-emerald-300';
  }
  if (value === 'Bearish' || value === 'Risk-Off' || value === 'NO_BUY' || value === 'DOWN') {
    return 'text-rose-300';
  }
  return 'text-amber-200';
};

const formatCurrency = (value) => (
  value != null && value !== 'N/A' ? `INR ${Number(value).toLocaleString()}` : 'N/A'
);

const wait = (ms) => new Promise((resolve) => {
  window.setTimeout(resolve, ms);
});

function Dashboard() {
  const { user, logout } = useContext(AuthContext);
  const [ticker, setTicker] = useState('RELIANCE.NS');
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [data, setData] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [news, setNews] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [predictionError, setPredictionError] = useState('');
  const [loading, setLoading] = useState(true);
  const [marketError, setMarketError] = useState('');
  const [loadingMessage, setLoadingMessage] = useState('Loading live market workspace...');
  const [predictionLoading, setPredictionLoading] = useState(false);
  const [providerStatus, setProviderStatus] = useState({ market_provider: 'unknown', market_provider_status: 'connecting' });
  const [timeframe, setTimeframe] = useState('1d');
  const searchBoxRef = useRef(null);
  const initialFetchDoneRef = useRef(false);
  const skipNextTimeframeFetchRef = useRef(false);
  const activeRequestRef = useRef(0);

  const fetchMarketData = async (requestedTicker, requestedTimeframe = timeframe) => {
    const requestId = activeRequestRef.current + 1;
    activeRequestRef.current = requestId;
    const activeTicker = (requestedTicker || ticker || '').trim().toUpperCase();
    const timeframeConfig = TIMEFRAMES.find((item) => item.id === requestedTimeframe) || TIMEFRAMES[0];
    const shouldExpectSlowLiveFeed = activeTicker.endsWith('.NS') || activeTicker.endsWith('.BO');

    if (!activeTicker) return;
    if (activeTicker !== ticker) {
      setTicker(activeTicker);
    }

    setLoading(true);
    setMarketError('');
    setPredictionError('');
    setLoadingMessage('Loading live market workspace...');
    setPredictionLoading(false);
    setPrediction(null);
    setData(null);
    setChartData([]);
    setNews([]);

    try {
      let marketRes = null;
      let histRes = [];
      let newsRes = [];
      const maxAttempts = shouldExpectSlowLiveFeed ? 18 : 4;

      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        if (attempt > 0) {
          setLoadingMessage(
            shouldExpectSlowLiveFeed
              ? `Waiting for live Upstox feed... attempt ${attempt + 1} of ${maxAttempts}`
              : `Retrying live market fetch... attempt ${attempt + 1} of ${maxAttempts}`,
          );
        }
        [marketRes, histRes, newsRes] = await Promise.all([
          marketService.getTickerData(activeTicker),
          marketService.getHistoricalData(activeTicker, timeframeConfig.period, timeframeConfig.id).catch(() => []),
          marketService.getNewsData(activeTicker).catch(() => []),
        ]);

        const hasPrice = marketRes?.current_price != null;
        const hasChart = Array.isArray(histRes) && histRes.length > 0;
        const shouldRetry = (!hasPrice || !hasChart) && attempt < maxAttempts - 1;
        if (!shouldRetry) {
          break;
        }
        await wait(shouldExpectSlowLiveFeed ? 5000 : 2500);
      }

      if (activeRequestRef.current !== requestId) {
        return;
      }

      setData(marketRes);
      setChartData(Array.isArray(histRes) ? histRes : []);
      setNews(Array.isArray(newsRes) ? newsRes : []);
    } catch (error) {
      if (activeRequestRef.current !== requestId) {
        return;
      }
      console.error('Failed to fetch market data pipelines:', error);
      setMarketError(error.response?.data?.detail || 'Unable to fetch market data right now.');
      setData(null);
      setChartData([]);
      setNews([]);
      setPrediction(null);
      setPredictionError('');
      setPredictionLoading(false);
    } finally {
      if (activeRequestRef.current === requestId) {
        setLoadingMessage('');
        setLoading(false);
      }
    }
  };

  const runPrediction = async () => {
    if (!data?.current_price || loading) {
      setPredictionError('Load live stock data first, then run prediction.');
      return;
    }

    setPredictionLoading(true);
    setPredictionError('');
    setPrediction(null);
    try {
      const predRes = await marketService.getPredictionData(
        ticker,
        data.current_price,
        'NEUTRAL',
        '1d',
      );
      setPrediction(predRes);
    } catch (error) {
      console.error('Prediction fetch failed:', error);
      setPrediction(null);
      setPredictionError(error.response?.data?.detail || 'Live prediction is unavailable right now.');
    } finally {
      setPredictionLoading(false);
    }
  };

  useEffect(() => {
    if (initialFetchDoneRef.current) {
      return;
    }
    initialFetchDoneRef.current = true;
    skipNextTimeframeFetchRef.current = true;
    fetchMarketData('RELIANCE.NS', '1d');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let mounted = true;

    const loadHealth = async () => {
      try {
        const status = await marketService.getHealthStatus();
        if (mounted) {
          setProviderStatus(status);
        }
      } catch (error) {
        if (mounted) {
          setProviderStatus({ market_provider: 'unknown', market_provider_status: 'unavailable' });
        }
      }
    };

    loadHealth();
    const timer = window.setInterval(loadHealth, 10000);

    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!initialFetchDoneRef.current) {
      return;
    }
    if (skipNextTimeframeFetchRef.current) {
      skipNextTimeframeFetchRef.current = false;
      return;
    }
    fetchMarketData(ticker, timeframe);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeframe]);

  useEffect(() => {
    const query = ticker.trim();
    if (!isSearchFocused || query.length < 2 || query.includes('.')) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setSearchLoading(true);
        const result = await marketService.getSearchSuggestions(query, 8);
        setSuggestions(Array.isArray(result) ? result : []);
        setShowSuggestions(true);
      } catch (error) {
        console.error('Search suggestion fetch failed:', error);
        setSuggestions([]);
      } finally {
        setSearchLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [ticker, isSearchFocused]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchBoxRef.current && !searchBoxRef.current.contains(event.target)) {
        setShowSuggestions(false);
        setIsSearchFocused(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectSuggestion = (symbol) => {
    setTicker(symbol);
    setShowSuggestions(false);
    setIsSearchFocused(false);
    fetchMarketData(symbol, timeframe);
  };

  const activeTimeframe = TIMEFRAMES.find((item) => item.id === timeframe) || TIMEFRAMES[0];
  const decision = prediction?.decision || 'WAIT';
  const decisionStyles = decisionTheme(decision);
  const agentInsights = prediction?.agent_insights || {};
  const priceText = formatCurrency(data?.current_price);
  const chartMeta = chartData[0] || {};
  const providerBadge =
    providerStatus.market_provider === 'upstox'
      ? providerStatus.market_provider_status === 'connected'
        ? { label: 'Upstox Connected', className: 'bg-emerald-500/15 text-emerald-200 border-emerald-400/25' }
        : { label: 'Connecting to Upstox', className: 'bg-amber-500/15 text-amber-100 border-amber-400/25' }
      : providerStatus.market_provider_status === 'unavailable'
        ? { label: 'Provider Unavailable', className: 'bg-rose-500/15 text-rose-100 border-rose-400/25' }
        : { label: 'Public Fallback Mode', className: 'bg-slate-500/15 text-slate-200 border-slate-300/20' };
  const changeText =
    data?.current_price != null
      ? `${data?.regular_market_change >= 0 ? '+' : ''}${data?.regular_market_change?.toFixed(2)} (${data?.regular_market_change_percent?.toFixed(2)}%)`
      : 'Price unavailable';

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(20,184,166,0.18),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(245,158,11,0.16),_transparent_22%),linear-gradient(160deg,_#020617_0%,_#111827_42%,_#0f172a_100%)] text-slate-100 p-4 md:p-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-8 rounded-[28px] border border-white/10 bg-slate-950/55 px-5 py-5 shadow-[0_25px_80px_rgba(2,6,23,0.55)] backdrop-blur-xl md:px-8">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.45em] text-teal-200/70">AI Trading Workspace</p>
              <div className={`mt-3 inline-flex rounded-full border px-3 py-1 text-xs font-medium ${providerBadge.className}`}>
                {providerBadge.label}
              </div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white md:text-4xl">
                Agent-Orchestrated Market Dashboard
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-slate-300">
                Track live price structure, inspect what each agent is seeing, and get a single decision with confidence.
              </p>
            </div>

            <div className="flex flex-col gap-4 xl:items-end">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="relative min-w-[280px]" ref={searchBoxRef}>
                  <input
                    type="text"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value)}
                    onFocus={() => {
                      setIsSearchFocused(true);
                      setShowSuggestions(suggestions.length > 0);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        setShowSuggestions(false);
                        setIsSearchFocused(false);
                        fetchMarketData(ticker, timeframe);
                      }
                    }}
                    placeholder="Search ticker, for example TCS.NS"
                    className="w-full rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-white outline-none transition focus:border-teal-300/60 focus:bg-slate-900"
                  />
                  {showSuggestions && (
                    <div className="absolute top-14 left-0 z-30 w-full overflow-hidden rounded-2xl border border-white/10 bg-slate-950/95 shadow-2xl">
                      {searchLoading && <div className="px-4 py-3 text-xs text-slate-400">Searching instruments...</div>}
                      {!searchLoading && suggestions.length === 0 && (
                        <div className="px-4 py-3 text-xs text-slate-400">No matching instruments found.</div>
                      )}
                      {!searchLoading && suggestions.map((item) => (
                        <button
                          key={item.symbol}
                          type="button"
                          onClick={() => handleSelectSuggestion(item.symbol)}
                          className="w-full border-b border-white/5 px-4 py-3 text-left transition hover:bg-white/5 last:border-b-0"
                        >
                          <div className="text-sm font-semibold text-white">{item.symbol}</div>
                          <div className="text-xs text-slate-400">
                            {item.name}
                            {item.exchange ? ` - ${item.exchange}` : ''}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <button
                  onClick={() => fetchMarketData(ticker, timeframe)}
                  className="inline-flex items-center justify-center rounded-2xl border border-teal-300/20 bg-teal-300/10 px-4 py-3 text-sm font-medium text-teal-100 transition hover:bg-teal-300/20"
                >
                  <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                </button>
              </div>

              <div className="flex items-center gap-3 text-sm text-slate-300">
                <span>
                  Logged in as <span className="font-semibold text-white">{user.username}</span>
                </span>
                <button
                  onClick={logout}
                  className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm transition hover:border-rose-300/30 hover:text-rose-200"
                >
                  <LogOut size={15} /> Logout
                </button>
              </div>
            </div>
          </div>
        </header>

        {marketError && (
          <div className="mb-6 rounded-2xl border border-rose-400/25 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {marketError}
          </div>
        )}

        <main className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_1.8fr]">
          <section className="space-y-6">
            <div className="rounded-[28px] border border-white/10 bg-slate-950/60 p-6 shadow-[0_20px_80px_rgba(2,6,23,0.45)] backdrop-blur-xl">
              <div className="flex flex-col gap-6">
                <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.35em] text-slate-400">Instrument</p>
                    <h2 className="mt-2 text-3xl font-semibold text-white">{data?.ticker || ticker}</h2>
                    <p className="mt-2 text-sm text-slate-300">
                      {data?.company_name || 'Market instrument'} - {data?.sector || 'Sector unavailable'}
                    </p>
                  </div>

                  <div className="rounded-3xl border border-white/10 bg-white/5 px-5 py-4 text-right">
                    <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Spot Price</p>
                    <p className="mt-2 text-3xl font-semibold text-white">{priceText}</p>
                    <p className={`mt-1 text-sm ${data?.regular_market_change >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                      {changeText}
                    </p>
                  </div>
                </div>

                <div className={`rounded-[26px] border px-5 py-5 ${decisionStyles.badge}`}>
                  <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.35em] opacity-80">Final Decision</p>
                      <div className="mt-2 flex items-center gap-3">
                        <span className="text-3xl font-semibold text-white">{decision.replace('_', ' ')}</span>
                        <span className="rounded-full border border-white/15 px-3 py-1 text-xs font-medium text-white/85">
                          Confidence {prediction?.confidence_score ?? 0}%
                        </span>
                      </div>
                      <p className="mt-3 max-w-xl text-sm text-slate-100/85">
                        {predictionLoading
                          ? 'Live agents are still synthesizing the market view.'
                          : prediction?.decision_summary || 'Load the stock first, then click Check Prediction to run the agent pipeline.'}
                      </p>
                      <button
                        type="button"
                        onClick={runPrediction}
                        disabled={predictionLoading || loading || data?.current_price == null}
                        className="mt-4 inline-flex items-center gap-2 rounded-full border border-amber-300/30 bg-amber-300/10 px-4 py-2 text-sm font-medium text-amber-100 transition hover:bg-amber-300/20 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Sparkles size={15} />
                        {predictionLoading ? 'Checking Prediction...' : 'Check Prediction'}
                      </button>
                      {predictionError && (
                        <p className="mt-3 text-sm text-rose-100/85">{predictionError}</p>
                      )}
                    </div>
                    <div className="grid min-w-[270px] grid-cols-3 gap-3 text-center text-sm">
                      <div className="rounded-2xl bg-slate-950/35 px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-300/75">Up</p>
                        <p className="mt-2 min-h-[28px] font-semibold text-white">
                          {prediction?.probabilities?.up != null ? `${Math.round(prediction.probabilities.up * 100)}%` : '--'}
                        </p>
                      </div>
                      <div className="rounded-2xl bg-slate-950/35 px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-300/75">Down</p>
                        <p className="mt-2 min-h-[28px] font-semibold text-white">
                          {prediction?.probabilities?.down != null ? `${Math.round(prediction.probabilities.down * 100)}%` : '--'}
                        </p>
                      </div>
                      <div className="rounded-2xl bg-slate-950/35 px-3 py-3">
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-300/75">Sideways</p>
                        <p className="mt-2 min-h-[28px] font-semibold text-white">
                          {prediction?.probabilities?.sideways != null ? `${Math.round(prediction.probabilities.sideways * 100)}%` : '--'}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-2xl border border-white/8 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Expected Range</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {formatCurrency(prediction?.lower_bound)} to {formatCurrency(prediction?.upper_bound)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Market Timestamp</p>
                    <p className="mt-2 text-sm font-medium text-white">
                      {prediction?.market_timestamp ? new Date(prediction.market_timestamp).toLocaleString() : 'N/A'}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">52 Week High</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {formatCurrency(data?.fifty_two_week_high)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Missing Signals</p>
                    <p className="mt-2 text-lg font-semibold text-white">{prediction?.missing_data?.length ?? 0}</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-white/10 bg-slate-950/60 p-6 shadow-[0_20px_80px_rgba(2,6,23,0.45)] backdrop-blur-xl">
              <div className="mb-4 flex items-center gap-3">
                <Activity className="text-amber-200" size={18} />
                <h3 className="text-lg font-semibold text-white">Agent Insights</h3>
              </div>
              <div className="space-y-4">
                {!prediction && !predictionLoading && (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 px-4 py-5 text-sm text-slate-300">
                    Click Check Prediction to generate live agent insights for this stock.
                  </div>
                )}
                {predictionLoading && (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 px-4 py-5 text-sm text-slate-300">
                    Live agent analysis is still loading. The dashboard will fill these cards when the prediction pipeline finishes.
                  </div>
                )}
                {!predictionLoading && prediction && Object.entries(AGENT_META).map(([key, meta]) => {
                  const insight = agentInsights[key];
                  const vote = prediction?.agent_votes?.[key]?.vote;
                  const Icon = meta.icon;

                  return (
                    <div key={key} className="rounded-2xl border border-white/8 bg-white/5 p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <div className="rounded-2xl bg-slate-900/70 p-2">
                            <Icon size={16} className="text-teal-200" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-white">{meta.label}</p>
                            <p className={`text-xs font-medium ${voteTone(vote)}`}>{vote || 'Awaiting signal'}</p>
                          </div>
                        </div>
                        <p className="text-xs text-slate-400">
                          {prediction?.agent_votes?.[key]?.reason || ''}
                        </p>
                      </div>
                      <p className="mt-3 text-sm text-slate-200">
                        {insight?.summary || 'This agent has not returned a detailed insight yet.'}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(insight?.details || []).map((item) => (
                          <span
                            key={item}
                            className="rounded-full border border-white/8 bg-slate-900/70 px-3 py-1 text-xs text-slate-300"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>

          <section className="space-y-6">
            <div className="rounded-[28px] border border-white/10 bg-slate-950/60 p-6 shadow-[0_20px_80px_rgba(2,6,23,0.45)] backdrop-blur-xl">
              <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-slate-400">Candlestick Structure</p>
                  <h3 className="mt-2 text-2xl font-semibold text-white">
                    {activeTimeframe.label} price action for {data?.ticker || ticker}
                  </h3>
                  <p className="mt-2 text-sm text-slate-400">
                    Source: {chartMeta.provider ? chartMeta.provider.toUpperCase() : 'N/A'}
                    {chartMeta.source_interval ? ` - raw interval ${chartMeta.source_interval}` : ''}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {TIMEFRAMES.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setTimeframe(item.id)}
                      className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                        timeframe === item.id
                          ? 'bg-amber-300 text-slate-950'
                          : 'border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10'
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="relative h-[430px] overflow-hidden rounded-[24px] border border-white/8 bg-[linear-gradient(180deg,rgba(15,23,42,0.92),rgba(10,15,29,0.98))] p-3">
                {loading && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/55 backdrop-blur-sm">
                    <div className="flex flex-col items-center gap-3 text-center">
                      <BarChart2 className="animate-pulse text-teal-200" />
                      <p className="text-xs uppercase tracking-[0.25em] text-slate-300">
                        {loadingMessage || 'Loading live chart'}
                      </p>
                    </div>
                  </div>
                )}
                {chartData.length > 0 ? (
                  <CandlestickChart data={chartData} timeframe={timeframe} />
                ) : (
                  !loading && (
                    <div className="flex h-full items-center justify-center text-sm text-slate-400">
                      Historical chart data is unavailable for this timeframe right now.
                    </div>
                  )
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-[28px] border border-white/10 bg-slate-950/60 p-6 shadow-[0_20px_80px_rgba(2,6,23,0.45)] backdrop-blur-xl">
                <div className="mb-4 flex items-center gap-3">
                  <Newspaper className="text-teal-200" size={18} />
                  <h3 className="text-lg font-semibold text-white">Live Sentiment Feed</h3>
                </div>
                <div className="space-y-3">
                  {news.length > 0 ? (
                    news.map((item, idx) => (
                      <a
                        key={`${item.title}-${idx}`}
                        href={item.link}
                        target="_blank"
                        rel="noreferrer"
                        className="block rounded-2xl border border-white/8 bg-white/5 p-4 transition hover:border-teal-300/25 hover:bg-white/8"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-medium leading-6 text-slate-100">{item.title}</p>
                          <span className={`rounded-full px-3 py-1 text-[11px] font-medium ${
                            item.sentiment === 'POSITIVE'
                              ? 'bg-emerald-500/15 text-emerald-200'
                              : item.sentiment === 'NEGATIVE'
                                ? 'bg-rose-500/15 text-rose-200'
                                : 'bg-amber-500/15 text-amber-100'
                          }`}>
                            {item.sentiment}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-slate-400">
                          {item.publisher} - {item.timestamp ? new Date(item.timestamp * 1000).toLocaleString() : 'Timestamp unavailable'}
                        </p>
                      </a>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 px-4 py-6 text-sm text-slate-400">
                      No live headlines are available for this ticker right now.
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-[28px] border border-white/10 bg-slate-950/60 p-6 shadow-[0_20px_80px_rgba(2,6,23,0.45)] backdrop-blur-xl">
                <div className="mb-4 flex items-center gap-3">
                  <ShieldCheck className="text-amber-200" size={18} />
                  <h3 className="text-lg font-semibold text-white">Confidence Breakdown</h3>
                </div>
                <div className="space-y-4">
                  {!prediction && !predictionLoading && (
                    <div className="rounded-2xl bg-white/5 p-4 text-sm text-slate-300">
                      Confidence breakdown will appear after you run Check Prediction.
                    </div>
                  )}
                  {predictionLoading && (
                    <div className="rounded-2xl bg-white/5 p-4 text-sm text-slate-300">
                      Waiting for confidence factors from the live decision engine...
                    </div>
                  )}
                  <div className="rounded-2xl bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Model</p>
                    <p className="mt-2 text-sm font-semibold text-white">
                      {prediction?.model_type || 'Multi-Agent Signal Fusion'}
                    </p>
                  </div>
                  <div className="rounded-2xl bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Agreement</p>
                    <p className="mt-2 text-2xl font-semibold text-white">
                      {prediction?.confidence_factors?.agreement != null ? `${Math.round(prediction.confidence_factors.agreement * 100)}%` : '--'}
                    </p>
                  </div>
                  <div className="rounded-2xl bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Reliability</p>
                    <p className="mt-2 text-2xl font-semibold text-white">
                      {prediction?.confidence_factors?.reliability != null ? `${Math.round(prediction.confidence_factors.reliability * 100)}%` : '--'}
                    </p>
                  </div>
                  <div className="rounded-2xl bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Freshness</p>
                    <p className="mt-2 text-2xl font-semibold text-white">
                      {prediction?.confidence_factors?.freshness != null ? `${Math.round(prediction.confidence_factors.freshness * 100)}%` : '--'}
                    </p>
                  </div>
                  <div className="rounded-2xl bg-white/5 p-4">
                    <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Top Driver</p>
                    <p className="mt-2 text-sm font-medium text-white">
                      {prediction?.top_drivers?.[0] || 'No driver identified yet.'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/auth" element={<Auth />} />
          <Route
            path="/"
            element={(
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            )}
          />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
