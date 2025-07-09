import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import App from './App';

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};

Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

// Mock fetch
global.fetch = jest.fn();

describe('App Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders login form when not authenticated', () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    render(<App />);
    expect(screen.getByText('Cowans Office Supplies Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Sign in to manage your product synchronization')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
  });

  it('renders application correctly', () => {
    mockLocalStorage.getItem.mockReturnValue(null);
    render(<App />);
    expect(screen.getByText('Cowans Office Supplies Dashboard')).toBeInTheDocument();
    // App can render in either authenticated or unauthenticated state
  });
});