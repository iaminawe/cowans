import React, { useState } from 'react';
import './styles.css';
import { DashboardLayout, DashboardSection } from './components/DashboardLayout';
import { SyncTrigger } from './components/SyncTrigger';
import { LogViewer } from './components/LogViewer';

interface LogEntry {
  id: string;
  timestamp: string;
  status: 'success' | 'error' | 'running';
  message: string;
  details?: string;
}

function App() {
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: '1', timestamp: '2025-05-30 14:00:00', status: 'success', message: 'Initial sync completed' },
    { id: '2', timestamp: '2025-05-30 14:05:00', status: 'error', message: 'Failed to update product X', details: 'API error' },
  ]);

  const handleSync = () => {
    alert('Sync triggered!');
  };

  return (
    <DashboardLayout>
      <DashboardSection>
        <SyncTrigger onSync={handleSync} />
      </DashboardSection>
      <DashboardSection>
        <LogViewer logs={logs} />
      </DashboardSection>
    </DashboardLayout>
  );
}

export default App;