import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import SyncControl from './SyncControl';

describe('SyncControl Component', () => {
  it('renders the SyncControl component', () => {
    render(<SyncControl />);
    expect(screen.getByRole('heading', { name: 'Sync Control' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sync Now' })).toBeInTheDocument();
  });
});