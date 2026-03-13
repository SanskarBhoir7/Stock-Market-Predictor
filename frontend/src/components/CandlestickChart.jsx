import React, { useEffect, useRef } from 'react';
import { createChart, ColorType } from 'lightweight-charts';

export const CandlestickChart = ({ data, colors: {
    backgroundColor = 'transparent',
    textColor = '#9ca3af',
} = {} }) => {
    const chartContainerRef = useRef();
    const chartRef = useRef(null);

    useEffect(() => {
        if (!data || data.length === 0) return;
        
        // Setup chart instances
        const handleResize = () => {
            if (chartRef.current && chartContainerRef.current) {
               chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        try {
            if (!chartContainerRef.current) return;

            const chart = createChart(chartContainerRef.current, {
                layout: {
                    background: { type: ColorType.Solid, color: backgroundColor },
                    textColor,
                },
                width: chartContainerRef.current.clientWidth || 600,
                height: 400,
                grid: {
                    vertLines: { color: 'rgba(192, 132, 252, 0.1)' },
                    horzLines: { color: 'rgba(192, 132, 252, 0.1)' },
                },
                rightPriceScale: {
                    borderVisible: false,
                },
                timeScale: {
                    borderVisible: false,
                    timeVisible: true,
                    secondsVisible: false,
                },
                crosshair: {
                    mode: 1, 
                }
            });
            
            chartRef.current = chart;

            // Formulate Candlestick logic
            const candlestickSeries = chart.addCandlestickSeries({
                upColor: '#22c55e', 
                downColor: '#ef4444', 
                borderVisible: false,
                wickUpColor: '#22c55e', 
                wickDownColor: '#ef4444', 
            });

            // Parse Array
            const dataMap = new Map();
            for (let i = 0; i < data.length; i++) {
                 const item = data[i];
                 if (
                     isNaN(item.open) || item.open === null ||
                     isNaN(item.high) || item.high === null ||
                     isNaN(item.low) || item.low === null ||
                     isNaN(item.close) || item.close === null ||
                     !item.time
                 ) continue;
                 
                 const dateParsed = new Date(item.time);
                 if (isNaN(dateParsed.getTime())) continue;

                 const businessDayStr = dateParsed.toISOString().split('T')[0];
                 dataMap.set(businessDayStr, {
                     time: businessDayStr,
                     open: Number(item.open),
                     high: Number(item.high),
                     low: Number(item.low),
                     close: Number(item.close)
                 });
            }
            
            const safeData = Array.from(dataMap.values());
            safeData.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
            
            if (safeData.length > 0) {
                const verifiedData = [safeData[0]];
                for (let i = 1; i < safeData.length; i++) {
                    if (new Date(safeData[i].time).getTime() > new Date(verifiedData[verifiedData.length - 1].time).getTime()) {
                         verifiedData.push(safeData[i]);
                    }
                }
                candlestickSeries.setData(verifiedData);
                chart.timeScale().fitContent();
            }

        } catch (error) {
            console.error("Candlestick Engine Engine CRASH caught completely:", error);
        }

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }
        };
    }, [data, backgroundColor, textColor]);

    return (
        <div ref={chartContainerRef} className="w-full h-full relative z-20" />
    );
};
