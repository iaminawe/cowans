import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LogViewer } from './LogViewer';

describe('LogViewer Component', () => {
  it('renders the LogViewer component', () => {
    render(<LogViewer logs={[]} />);
    expect(screen.getByText('No sync logs available')).toBeInTheDocument();
  });
});