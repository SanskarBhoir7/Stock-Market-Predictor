import { render, screen } from '@testing-library/react';
import App from './App';
import { BrowserRouter } from 'react-router-dom';

test('renders Stock Market Predictor text', () => {
    // We render inside BrowserRouter since App uses Routes
    render(
        <BrowserRouter>
            <App />
        </BrowserRouter>
    );
    const linkElement = screen.getByText(/Stock Market Predictor/i);
    expect(linkElement).toBeInTheDocument();
});
