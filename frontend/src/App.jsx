import React, { useContext, useEffect, useState, useCallback, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, AuthContext } from './context/AuthContext';
import Auth from './pages/Auth';
import { LogOut, RefreshCw, BarChart2 } from 'lucide-react';
import { marketService } from './services/api';
import { CandlestickChart } from './components/CandlestickChart';

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useContext(AuthContext);
  
  if (loading) return <div className="min-h-screen bg-gray-950 flex items-center justify-center text-white font-mono animate-pulse">Initializing Trading Systems...</div>;
  if (!user) return <Navigate to="/auth" />;

  return children;
};

function Dashboard() {
  const { user, logout } = useContext(AuthContext);
  const [ticker, setTicker] = useState("RELIANCE.NS");
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [data, setData] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [news, setNews] = useState([]);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);
  const searchBoxRef = useRef(null);

  const fetchMarketData = useCallback(async (requestedTicker) => {
    const activeTicker = (requestedTicker || ticker || "").trim().toUpperCase();
    if (!activeTicker) return;
    if (activeTicker !== ticker) {
      setTicker(activeTicker);
    }
    setLoading(true);
    try {
      const [marketRes, histRes, newsRes] = await Promise.all([
         marketService.getTickerData(activeTicker),
         marketService.getHistoricalData(activeTicker, '1y'),
         marketService.getNewsData(activeTicker)
      ]);
      setData(marketRes);
      setChartData(histRes);
      setNews(newsRes);

      // Now fetch prediction with dependent variables (Price & Sentiment)
      if (marketRes.current_price) {
          // Find overall sentiment tag to feed GAN
          const overallSentiment = newsRes.length > 0 && newsRes[0].sentiment === 'POSITIVE' ? 'POSITIVE' : 'NEUTRAL';
          const predRes = await marketService.getPredictionData(activeTicker, marketRes.current_price, overallSentiment, '1d');
          setPrediction(predRes);
      }

    } catch (error) {
      console.error("Failed to fetch market data pipelines:", error);
    } finally {
      setLoading(false);
    }
  }, [ticker]);

  useEffect(() => {
    fetchMarketData("RELIANCE.NS");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const query = ticker.trim();
    if (query.length < 2) {
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
        console.error("Search suggestion fetch failed:", error);
        setSuggestions([]);
      } finally {
        setSearchLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [ticker]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchBoxRef.current && !searchBoxRef.current.contains(event.target)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectSuggestion = (symbol) => {
    setTicker(symbol);
    setShowSuggestions(false);
    fetchMarketData(symbol);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-black text-white p-8 font-sans transition-all duration-500">
      <header className="flex items-center justify-between pb-6 border-b border-gray-800">
        <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-cyan-400">
          AI Trading Engine
        </h1>
        <div className="flex items-center gap-4">
          <div className="relative" ref={searchBoxRef}>
            <input 
               type="text" 
               value={ticker} 
               onChange={(e) => setTicker(e.target.value)}
               onFocus={() => setShowSuggestions(suggestions.length > 0)}
               onKeyDown={(e) => {
                 if (e.key === 'Enter') {
                   setShowSuggestions(false);
                   fetchMarketData(ticker);
                 }
               }}
               placeholder="Search Ticker (e.g. TCS.NS)"
               className="bg-gray-900/50 border border-gray-700 focus:border-purple-500 rounded-lg px-4 py-2 text-sm outline-none font-mono w-72"
            />
            {showSuggestions && (
              <div className="absolute top-11 left-0 z-30 w-full bg-gray-900 border border-gray-700 rounded-lg shadow-2xl max-h-72 overflow-y-auto">
                {searchLoading && (
                  <div className="px-3 py-2 text-xs text-gray-400">Searching...</div>
                )}
                {!searchLoading && suggestions.length === 0 && (
                  <div className="px-3 py-2 text-xs text-gray-400">No recommendations found.</div>
                )}
                {!searchLoading && suggestions.map((item) => (
                  <button
                    key={item.symbol}
                    type="button"
                    onClick={() => handleSelectSuggestion(item.symbol)}
                    className="w-full text-left px-3 py-2 hover:bg-gray-800 transition border-b border-gray-800 last:border-b-0"
                  >
                    <div className="text-sm text-white font-semibold">{item.symbol}</div>
                    <div className="text-xs text-gray-400 truncate">{item.name}{item.exchange ? ` • ${item.exchange}` : ''}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
          <button onClick={() => fetchMarketData(ticker)} className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition">
             <RefreshCw size={18} className={loading ? "animate-spin text-purple-400" : "text-gray-400"} />
          </button>
        </div>
        <nav className="flex items-center gap-6">
          <div className="text-gray-400 font-medium">Logged in as <span className="text-white font-bold">{user.username}</span></div>
          <button 
            onClick={logout}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-gray-800/80 hover:bg-red-500/20 hover:text-red-400 hover:border-red-500/50 border border-gray-700 transition-all duration-300"
          >
            <LogOut size={16} /> Disconnect
          </button>
        </nav>
      </header>

      <main className="mt-10 grid grid-cols-1 lg:grid-cols-3 gap-8 relative z-10">
        {/* Left Column: Ticker info and Real-time data */}
        <section className="col-span-1 border border-gray-800 bg-gray-900/60 backdrop-blur-xl rounded-2xl p-6 shadow-2xl hover:border-purple-500/50 transition duration-500 group relative overflow-hidden flex flex-col">
          {loading && <div className="absolute inset-0 bg-gray-900/80 backdrop-blur-sm z-20 flex items-center justify-center font-mono text-purple-400 animate-pulse">ALLOCATING VECTORS...</div>}
          
          <div className="flex justify-between items-start mb-6">
            <div>
              <h2 className="text-4xl font-extrabold group-hover:text-purple-400 transition">{data?.ticker || '---'}</h2>
              <p className="text-gray-400 mt-1 truncate w-48">{data?.company_name || '...'} • {data?.sector || '...'}</p>
            </div>
            <div className="text-right">
              <p className="text-3xl font-bold text-green-400">₹{data?.current_price?.toLocaleString() || '0.00'}</p>
              <p className={`text-sm font-medium ${data?.regular_market_change >= 0 ? 'text-green-500/80' : 'text-red-500/80'}`}>
                {data?.regular_market_change >= 0 ? '+' : ''}{data?.regular_market_change?.toFixed(2)} ({data?.regular_market_change_percent?.toFixed(2)}%)
              </p>
            </div>
          </div>
          
          <div className="space-y-4">
            <h3 className="text-sm uppercase tracking-widest text-gray-500 font-semibold mb-2">Multi-Agent Prediction Vector</h3>
            <div className="bg-purple-950/40 border border-purple-500/30 rounded-xl p-5 shadow-[0_0_15px_rgba(168,85,247,0.15)] relative overflow-hidden">
               <div className="absolute top-0 left-0 w-1 h-full bg-purple-500"></div>
              <p className="text-xs text-purple-300 uppercase tracking-wide">Target Range (Next 1 Day)</p>
              <p className="text-3xl font-extrabold text-white mt-2">
                ₹{prediction?.lower_bound?.toLocaleString() || '---'} - ₹{prediction?.upper_bound?.toLocaleString() || '---'}
              </p>
              <div className="flex items-center mt-3 gap-2">
                 <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
                 <p className="text-xs text-green-400 font-medium tracking-wide">CONFIDENCE: {prediction?.confidence_score || 0}% • Multi-Agent</p>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs">
                <span className="text-gray-400">Final Call:</span>
                <span className={`font-semibold ${prediction?.final_call === 'UP' ? 'text-green-400' : prediction?.final_call === 'DOWN' ? 'text-red-400' : 'text-yellow-400'}`}>
                  {prediction?.final_call || 'SIDEWAYS'}
                </span>
                <span className="text-gray-500">| Horizon: {prediction?.time_horizon || '1d'}</span>
              </div>
            </div>
          </div>

          <div className="mt-8 space-y-4 flex-grow">
            <h3 className="text-sm uppercase tracking-widest text-gray-500 font-semibold border-b border-gray-800 pb-2">Key Fundamentals</h3>
            <div className="grid grid-cols-2 gap-4 text-sm mt-4">
              <div className="bg-gray-800/40 p-3 rounded-lg border border-gray-800">
                <p className="text-gray-500 text-xs uppercase tracking-wide">Market Cap</p>
                <p className="font-bold text-lg text-gray-200 mt-1">{data?.market_cap || 'N/A'}</p>
              </div>
              <div className="bg-gray-800/40 p-3 rounded-lg border border-gray-800">
                <p className="text-gray-500 text-xs uppercase tracking-wide">P/E Ratio</p>
                <p className="font-bold text-lg text-gray-200 mt-1">{data?.pe_ratio !== 'N/A' ? Number(data?.pe_ratio).toFixed(2) : 'N/A'}</p>
              </div>
              <div className="bg-gray-800/40 p-3 rounded-lg border border-gray-800">
                <p className="text-gray-500 text-xs uppercase tracking-wide">Div Yield</p>
                <p className="font-bold text-lg text-gray-200 mt-1">{data?.div_yield || 'N/A'}</p>
              </div>
              <div className="bg-gray-800/40 p-3 rounded-lg border border-gray-800">
                <p className="text-gray-500 text-xs uppercase tracking-wide">52W High</p>
                <p className="font-bold text-lg text-gray-200 mt-1">₹{data?.fifty_two_week_high?.toLocaleString() || 'N/A'}</p>
              </div>
            </div>
          </div>
        </section>

        {/* Right Column: Charts and News */}
        <section className="col-span-2 space-y-6">
          <div className="border border-gray-800 bg-gray-900/60 backdrop-blur-xl rounded-2xl p-6 shadow-2xl h-[450px] relative overflow-hidden group">
             {loading && <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-cyan-900/20 to-transparent flex items-center justify-center z-10"><BarChart2 className="animate-bounce text-cyan-500" /></div>}
             {chartData.length > 0 && <CandlestickChart data={chartData} />}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="border border-gray-800 bg-gray-900/60 backdrop-blur-xl rounded-2xl p-6 shadow-2xl h-[260px] overflow-y-auto custom-scrollbar relative">
              <h3 className="text-sm uppercase tracking-widest text-gray-500 font-semibold mb-4 sticky top-0 bg-gray-900/90 py-1 z-10">Live Sentiment Agent Analysis</h3>
              <ul className="space-y-4">
                {news.length > 0 ? news.map((item, idx) => (
                    <li key={idx} className="flex gap-3 items-start bg-gray-800/30 p-3 rounded-lg border border-transparent hover:border-gray-700 transition">
                      <span className={`min-w-2.5 min-h-2.5 rounded-full mt-1.5 shadow-[0_0_8px_rgba(255,255,255,0.6)] ${item.sentiment === 'POSITIVE' ? 'bg-green-500' : item.sentiment === 'NEGATIVE' ? 'bg-red-500' : 'bg-gray-500'}`}></span>
                      <div>
                        <a href={item.link} target="_blank" rel="noreferrer" className="text-sm text-gray-300 hover:text-purple-400 font-medium leading-relaxed block transition">{item.title}</a>
                        <p className="text-xs text-gray-600 font-mono mt-1">{item.publisher} • {item.sentiment}</p>
                      </div>
                    </li>
                )) : (
                    <p className="text-gray-500 text-sm py-4 italic">No major news headlines detected for this sector today.</p>
                )}
              </ul>
            </div>
            <div className="border border-gray-800 bg-gray-900/60 backdrop-blur-xl rounded-2xl p-6 shadow-2xl relative overflow-hidden">
               <div className="absolute top-0 right-0 w-32 h-32 bg-cyan-500/10 rounded-full blur-3xl"></div>
              <h3 className="text-sm uppercase tracking-widest text-gray-500 font-semibold mb-4 relative z-10">Model Pipeline Metrics</h3>
              <div className="space-y-4 relative z-10">
                <div className="flex justify-between items-center bg-gray-800/40 p-3 rounded-lg border border-gray-700/50">
                  <span className="text-gray-400 text-sm">Active Model Architecture</span>
                  <span className="font-bold text-cyan-400 font-mono text-sm">{prediction?.model_type || 'Multi-Agent Signal Fusion'}</span>
                </div>
                <div className="flex justify-between items-center bg-gray-800/40 p-3 rounded-lg border border-gray-700/50">
                  <span className="text-gray-400 text-sm">Market Timestamp</span>
                  <span className="font-bold text-white font-mono text-xs">{prediction?.market_timestamp ? new Date(prediction.market_timestamp).toLocaleString() : 'N/A'}</span>
                </div>
                <div className="flex justify-between items-center bg-gray-800/40 p-3 rounded-lg border border-gray-700/50">
                  <span className="text-gray-400 text-sm">Missing Data Signals</span>
                  <span className="font-bold text-white font-mono text-sm">{prediction?.missing_data?.length ?? 0}</span>
                </div>
                <div className="bg-gray-800/40 p-3 rounded-lg border border-gray-700/50">
                  <span className="text-gray-400 text-sm block mb-1">Top Driver</span>
                  <span className="font-bold text-white text-sm">{prediction?.top_drivers?.[0] || 'Not available'}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
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
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } 
          />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;

