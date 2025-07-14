import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  Database,
  Download,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  FileText,
  FolderOpen,
  HardDrive,
  Wifi,
  WifiOff,
  Settings,
  Calendar,
  Search,
  Filter,
  FileSpreadsheet,
  ArrowRight
} from 'lucide-react';
import { useWebSocket } from '@/contexts/WebSocketContext';
import { apiClient } from '@/lib/api';

interface EtilizeSyncToolProps {
  className?: string;
}

// Local component types - these match the component's needs
interface LocalFTPConnectionStatus {
  connected: boolean;
  lastChecked: string;
  error?: string;
}

interface LocalFTPFile {
  name: string;
  size: number;
  modified: string;
  type: 'file' | 'directory';
  isNew: boolean;
}

interface ImportConfig {
  autoImport: boolean;
  importSchedule: 'manual' | 'hourly' | 'daily' | 'weekly';
  filePattern: string;
  targetDirectory: string;
  archiveProcessed: boolean;
  validateBeforeImport: boolean;
  notifyOnNew: boolean;
}

interface LocalImportJob {
  id: string;
  filename: string;
  status: 'queued' | 'downloading' | 'processing' | 'completed' | 'failed';
  progress: number;
  fileSize: number;
  downloadedSize: number;
  recordsProcessed: number;
  recordsTotal: number;
  startTime: string;
  endTime?: string;
  error?: string;
}

// Type adapters for API compatibility
function adaptFTPConnectionStatus(apiStatus: unknown): LocalFTPConnectionStatus {
  const status = apiStatus as Record<string, unknown>;
  return {
    connected: Boolean(status.connected),
    lastChecked: (status.lastChecked as string) || (status.last_connection as string) || new Date().toISOString(),
    error: status.error as string | undefined
  };
}

function adaptFTPFile(apiFile: unknown): LocalFTPFile {
  const file = apiFile as Record<string, unknown>;
  return {
    name: (file.name as string) || '',
    size: Number(file.size) || 0,
    modified: (file.modified as string) || new Date().toISOString(),
    type: (file.type as 'file' | 'directory') || 'file',
    isNew: Boolean(file.isNew)
  };
}

function adaptImportJob(apiJob: unknown): LocalImportJob {
  const job = apiJob as Record<string, unknown>;
  return {
    id: (job.id as string) || (job.job_id as string) || '',
    filename: (job.filename as string) || '',
    status: (job.status as LocalImportJob['status']) || 'queued',
    progress: Number(job.progress) || 0,
    fileSize: Number(job.fileSize || job.file_size) || 0,
    downloadedSize: Number(job.downloadedSize || job.downloaded_size) || 0,
    recordsProcessed: Number(job.recordsProcessed || job.processed_records) || 0,
    recordsTotal: Number(job.recordsTotal || job.total_records) || 0,
    startTime: (job.startTime as string) || (job.created_at as string) || new Date().toISOString(),
    endTime: (job.endTime as string) || (job.completed_at as string) || undefined,
    error: (job.error as string) || (job.error_message as string) || undefined
  };
}

export function EtilizeSyncTool({ className }: EtilizeSyncToolProps) {
  const [activeTab, setActiveTab] = useState<'monitor' | 'import' | 'history' | 'settings'>('monitor');
  const [ftpStatus, setFtpStatus] = useState<LocalFTPConnectionStatus>({
    connected: false,
    lastChecked: new Date().toISOString()
  });
  const [ftpFiles, setFtpFiles] = useState<LocalFTPFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [importConfig, setImportConfig] = useState<ImportConfig>({
    autoImport: false,
    importSchedule: 'manual',
    filePattern: '*.csv',
    targetDirectory: '/etilize',
    archiveProcessed: true,
    validateBeforeImport: true,
    notifyOnNew: true
  });
  const [currentJob, setCurrentJob] = useState<LocalImportJob | null>(null);
  const [importHistory, setImportHistory] = useState<LocalImportJob[]>([]);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const { subscribe, subscribeCustom, sendMessage, isConnected } = useWebSocket();

  useEffect(() => {
    checkFTPConnection();
    loadImportHistory();
  }, []);

  useEffect(() => {
    if (!isConnected) return;

    const unsubscribeFTPStatus = subscribeCustom('etilize-ftp-status', (data) => {
      setFtpStatus(adaptFTPConnectionStatus(data));
    });

    const unsubscribeNewFile = subscribeCustom('etilize-new-file', (data) => {
      const fileData = data as unknown as Record<string, unknown>;
      if (importConfig.notifyOnNew) {
        setSuccess(`New file detected: ${fileData.filename}`);
      }
      if (importConfig.autoImport) {
        handleImportFile(fileData.filename as string);
      } else {
        scanFTPDirectory();
      }
    });

    const unsubscribeImportProgress = subscribeCustom('etilize-import-progress', (data) => {
      const progressData = data as unknown as Record<string, unknown>;
      const adaptedJob = adaptImportJob(progressData.job);
      setCurrentJob(adaptedJob);
      
      if (adaptedJob.status === 'completed' || adaptedJob.status === 'failed') {
        setImportHistory(prev => [adaptedJob, ...prev]);
        if (adaptedJob.status === 'completed') {
          setSuccess(`Import completed: ${adaptedJob.recordsProcessed} records processed`);
        }
      }
    });

    return () => {
      unsubscribeFTPStatus();
      unsubscribeNewFile();
      unsubscribeImportProgress();
    };
  }, [subscribe, isConnected, importConfig]);

  const checkFTPConnection = async () => {
    setIsConnecting(true);
    setError(null);

    try {
      const status = await apiClient.checkEtilizeFTPConnection();
      setFtpStatus(adaptFTPConnectionStatus(status));
      
      if (status.connected) {
        scanFTPDirectory();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to check FTP connection');
      setFtpStatus(adaptFTPConnectionStatus({
        connected: false,
        lastChecked: new Date().toISOString(),
        error: 'Connection failed'
      }));
    } finally {
      setIsConnecting(false);
    }
  };

  const scanFTPDirectory = async () => {
    if (!ftpStatus.connected) return;

    setIsScanning(true);
    try {
      const response = await apiClient.scanEtilizeFTP(importConfig.targetDirectory);
      setFtpFiles(response.files.map(adaptFTPFile));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to scan FTP directory');
    } finally {
      setIsScanning(false);
    }
  };

  const loadImportHistory = async () => {
    try {
      const response = await apiClient.getEtilizeImportHistory();
      setImportHistory(response.jobs.map(adaptImportJob));
    } catch (err) {
      console.error('Failed to load import history:', err);
    }
  };

  const handleFileSelection = (filename: string, selected: boolean) => {
    setSelectedFiles(prev => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(filename);
      } else {
        newSet.delete(filename);
      }
      return newSet;
    });
  };

  const handleImportSelected = async () => {
    if (selectedFiles.size === 0) {
      setError('Please select at least one file to import');
      return;
    }

    for (const filename of Array.from(selectedFiles)) {
      await handleImportFile(filename);
    }
    
    setSelectedFiles(new Set());
  };

  const handleImportFile = async (filename: string) => {
    try {
      const response = await apiClient.startEtilizeImport({
        filename,
        validate: importConfig.validateBeforeImport,
        archive: importConfig.archiveProcessed
      });

      setCurrentJob(adaptImportJob({
        id: response.job_id,
        filename,
        status: 'queued',
        progress: 0,
        fileSize: 0,
        downloadedSize: 0,
        recordsProcessed: 0,
        recordsTotal: 0,
        startTime: new Date().toISOString()
      }));

      sendMessage({
        type: 'monitor-etilize-import',
        jobId: response.job_id
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start import');
    }
  };

  const handleConfigChange = (field: keyof ImportConfig, value: string | boolean) => {
    setImportConfig(prev => ({ ...prev, [field]: value }));
  };

  const saveConfiguration = async () => {
    try {
      await apiClient.saveEtilizeConfig(importConfig);
      setSuccess('Configuration saved successfully');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration');
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDuration = (start: string, end?: string): string => {
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const duration = Math.floor((endTime - startTime) / 1000);
    
    if (duration < 60) return `${duration}s`;
    const minutes = Math.floor(duration / 60);
    const seconds = duration % 60;
    return `${minutes}m ${seconds}s`;
  };

  return (
    <div className={cn("space-y-6", className)}>
      {error && (
        <Alert variant="destructive">
          <XCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert>
          <CheckCircle className="h-4 w-4" />
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {/* Connection Status */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>FTP Connection Status</CardTitle>
            <Button
              size="sm"
              variant="outline"
              onClick={checkFTPConnection}
              disabled={isConnecting}
            >
              {isConnecting ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {ftpStatus.connected ? (
                <Wifi className="h-6 w-6 text-green-500" />
              ) : (
                <WifiOff className="h-6 w-6 text-red-500" />
              )}
              <div>
                <p className="font-medium">
                  {ftpStatus.connected ? 'Connected' : 'Disconnected'}
                </p>
                <p className="text-sm text-muted-foreground">
                  Last checked: {new Date(ftpStatus.lastChecked).toLocaleTimeString()}
                </p>
              </div>
            </div>
            {ftpStatus.error && (
              <Badge variant="destructive">{ftpStatus.error}</Badge>
            )}
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="monitor" className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4" />
            Monitor
          </TabsTrigger>
          <TabsTrigger value="import" className="flex items-center gap-2">
            <Download className="h-4 w-4" />
            Import
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            History
          </TabsTrigger>
          <TabsTrigger value="settings" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* Monitor Tab */}
        <TabsContent value="monitor" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>FTP Directory</CardTitle>
                  <CardDescription>{importConfig.targetDirectory}</CardDescription>
                </div>
                <Button
                  size="sm"
                  onClick={scanFTPDirectory}
                  disabled={!ftpStatus.connected || isScanning}
                >
                  {isScanning ? (
                    <>
                      <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                      Scanning...
                    </>
                  ) : (
                    <>
                      <Search className="h-4 w-4 mr-2" />
                      Scan Directory
                    </>
                  )}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {!ftpStatus.connected ? (
                <div className="text-center py-8">
                  <WifiOff className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-muted-foreground">Not connected to FTP server</p>
                </div>
              ) : ftpFiles.length === 0 ? (
                <div className="text-center py-8">
                  <FolderOpen className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-muted-foreground">No files found</p>
                </div>
              ) : (
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2">
                    {ftpFiles.map((file) => (
                      <div
                        key={file.name}
                        className={cn(
                          "flex items-center justify-between p-3 border rounded-lg",
                          file.isNew && "border-green-500 bg-green-50"
                        )}
                      >
                        <div className="flex items-center gap-3">
                          {file.type === 'file' ? (
                            <FileSpreadsheet className="h-5 w-5 text-muted-foreground" />
                          ) : (
                            <FolderOpen className="h-5 w-5 text-muted-foreground" />
                          )}
                          <div>
                            <p className="font-medium">{file.name}</p>
                            <p className="text-sm text-muted-foreground">
                              {formatFileSize(file.size)} • Modified: {new Date(file.modified).toLocaleString()}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {file.isNew && <Badge variant="default">New</Badge>}
                          {file.type === 'file' && file.name.endsWith('.csv') && (
                            <Button
                              size="sm"
                              onClick={() => handleImportFile(file.name)}
                            >
                              Import
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Import Tab */}
        <TabsContent value="import" className="space-y-6">
          {currentJob ? (
            <Card>
              <CardHeader>
                <CardTitle>Import Progress</CardTitle>
                <CardDescription>{currentJob.filename}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>Overall Progress</span>
                    <span>{currentJob.progress.toFixed(1)}%</span>
                  </div>
                  <Progress value={currentJob.progress} />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Download Progress</p>
                    <p className="font-medium">
                      {formatFileSize(currentJob.downloadedSize)} / {formatFileSize(currentJob.fileSize)}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Records Processed</p>
                    <p className="font-medium">
                      {currentJob.recordsProcessed} / {currentJob.recordsTotal || '?'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <Badge variant={
                    currentJob.status === 'completed' ? 'default' :
                    currentJob.status === 'failed' ? 'destructive' :
                    'secondary'
                  }>
                    {currentJob.status}
                  </Badge>
                  <span className="text-sm text-muted-foreground">
                    Duration: {formatDuration(currentJob.startTime, currentJob.endTime)}
                  </span>
                </div>

                {currentJob.error && (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>{currentJob.error}</AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Manual Import</CardTitle>
                <CardDescription>Select files to import from FTP</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Available Files</Label>
                    <ScrollArea className="h-[300px] border rounded-md p-4">
                      {ftpFiles.filter(f => f.type === 'file' && f.name.endsWith('.csv')).length === 0 ? (
                        <p className="text-center text-muted-foreground">No CSV files available</p>
                      ) : (
                        <div className="space-y-2">
                          {ftpFiles
                            .filter(f => f.type === 'file' && f.name.endsWith('.csv'))
                            .map((file) => (
                              <label
                                key={file.name}
                                className="flex items-center space-x-3 cursor-pointer"
                              >
                                <input
                                  type="checkbox"
                                  checked={selectedFiles.has(file.name)}
                                  onChange={(e) => handleFileSelection(file.name, e.target.checked)}
                                  className="rounded"
                                />
                                <div className="flex-1">
                                  <p className="font-medium">{file.name}</p>
                                  <p className="text-sm text-muted-foreground">
                                    {formatFileSize(file.size)}
                                  </p>
                                </div>
                              </label>
                            ))}
                        </div>
                      )}
                    </ScrollArea>
                  </div>

                  {selectedFiles.size > 0 && (
                    <Button onClick={handleImportSelected} className="w-full">
                      <Download className="h-4 w-4 mr-2" />
                      Import {selectedFiles.size} File{selectedFiles.size > 1 ? 's' : ''}
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Import History</CardTitle>
              <CardDescription>Previous import operations</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[500px]">
                {importHistory.length === 0 ? (
                  <div className="text-center py-8">
                    <Clock className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                    <p className="text-muted-foreground">No import history</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {importHistory.map((job) => (
                      <Card key={job.id}>
                        <CardContent className="pt-6">
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              {job.status === 'completed' ? (
                                <CheckCircle className="h-5 w-5 text-green-500" />
                              ) : (
                                <XCircle className="h-5 w-5 text-red-500" />
                              )}
                              <h4 className="font-medium">{job.filename}</h4>
                            </div>
                            <Badge variant={job.status === 'completed' ? 'default' : 'destructive'}>
                              {job.status}
                            </Badge>
                          </div>
                          <div className="grid grid-cols-3 gap-4 text-sm">
                            <div>
                              <p className="text-muted-foreground">Records</p>
                              <p className="font-medium">{job.recordsProcessed}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Duration</p>
                              <p className="font-medium">{formatDuration(job.startTime, job.endTime)}</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Date</p>
                              <p className="font-medium">{new Date(job.startTime).toLocaleDateString()}</p>
                            </div>
                          </div>
                          {job.error && (
                            <p className="text-sm text-red-600 mt-2">{job.error}</p>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Import Configuration</CardTitle>
              <CardDescription>Configure automatic import settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Automatic Import</Label>
                    <p className="text-sm text-muted-foreground">
                      Automatically import new files when detected
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={importConfig.autoImport}
                    onChange={(e) => handleConfigChange('autoImport', e.target.checked)}
                    className="toggle"
                  />
                </div>

                {importConfig.autoImport && (
                  <div className="space-y-2">
                    <Label>Import Schedule</Label>
                    <Select
                      value={importConfig.importSchedule}
                      onValueChange={(value) => handleConfigChange('importSchedule', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="manual">Manual Only</SelectItem>
                        <SelectItem value="hourly">Every Hour</SelectItem>
                        <SelectItem value="daily">Daily</SelectItem>
                        <SelectItem value="weekly">Weekly</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="file-pattern">File Pattern</Label>
                <Input
                  id="file-pattern"
                  value={importConfig.filePattern}
                  onChange={(e) => handleConfigChange('filePattern', e.target.value)}
                  placeholder="*.csv"
                />
                <p className="text-xs text-muted-foreground">
                  Only files matching this pattern will be imported
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="target-directory">Target Directory</Label>
                <Input
                  id="target-directory"
                  value={importConfig.targetDirectory}
                  onChange={(e) => handleConfigChange('targetDirectory', e.target.value)}
                  placeholder="/etilize"
                />
              </div>

              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="validate-before"
                    checked={importConfig.validateBeforeImport}
                    onChange={(e) => handleConfigChange('validateBeforeImport', e.target.checked)}
                    className="rounded"
                  />
                  <Label htmlFor="validate-before" className="font-normal">
                    Validate files before import
                  </Label>
                </div>

                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="archive-processed"
                    checked={importConfig.archiveProcessed}
                    onChange={(e) => handleConfigChange('archiveProcessed', e.target.checked)}
                    className="rounded"
                  />
                  <Label htmlFor="archive-processed" className="font-normal">
                    Archive processed files
                  </Label>
                </div>

                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="notify-new"
                    checked={importConfig.notifyOnNew}
                    onChange={(e) => handleConfigChange('notifyOnNew', e.target.checked)}
                    className="rounded"
                  />
                  <Label htmlFor="notify-new" className="font-normal">
                    Notify when new files are detected
                  </Label>
                </div>
              </div>

              <Button onClick={saveConfiguration} className="w-full">
                Save Configuration
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}