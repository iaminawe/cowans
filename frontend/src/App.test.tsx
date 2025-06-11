import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from './App';

describe('App Component', () => {
  it('renders the DashboardLayout component', () => {
    render(<App />);
    expect(screen.getByText('Product Feed Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Manual Sync')).toBeInTheDocument();
    expect(screen.getByText('Sync History')).toBeInTheDocument();
  });
});