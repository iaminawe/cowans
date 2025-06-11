import React from 'react';
import { render, screen } from '@testing-library/react';
import LandingPage from './LandingPage';

describe('LandingPage Component', () => {
  it('should render the landing page', () => {
    render(<LandingPage />);
    const landingPageElement = screen.getByText(/Landing Page/i);
    expect(landingPageElement).toBeInTheDocument();
  });
});