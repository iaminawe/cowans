import React, { useState, useEffect, useCallback } from 'react';
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { 
  Upload, 
  FileText, 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertTriangle,
  Download,
  RefreshCw,
  Play,
  Pause,
  MoreHorizontal
} from 'lucide-react';
import { apiClient, type ImportHistoryItem, type ImportStatus, type ImportValidationResult } from '@/lib/api';

interface ImportManagerProps {
  className?: string;
}

interface ImportJob {
  id: string;
  status: ImportStatus;
  startTime: Date;
}

export function ImportManager({ className }: ImportManagerProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'history' | 'running'>('upload');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [validationResult, setValidationResult] = useState<ImportValidationResult | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [uploadedFilePath, setUploadedFilePath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // History and running imports
  const [importHistory, setImportHistory] = useState<ImportHistoryItem[]>([]);
  const [runningImports, setRunningImports] = useState<ImportJob[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Load import history
  const loadImportHistory = useCallback(async () => {
    try {
      setIsLoadingHistory(true);
      const response = await apiClient.getImportHistory();
      setImportHistory(response.history);
    } catch (err) {
      console.error('Failed to load import history:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  }, []);

  // Load data on mount
  useEffect(() => {
    loadImportHistory();
  }, [loadImportHistory]);

  // Poll running imports
  useEffect(() => {
    if (runningImports.length === 0) return;

    const interval = setInterval(async () => {
      const updatedJobs = await Promise.all(
        runningImports.map(async (job) => {
          try {
            const status = await apiClient.getImportStatus(job.id);
            return { ...job, status };
          } catch (err) {
            console.error(`Failed to get status for ${job.id}:`, err);
            return job;
          }
        })
      );

      // Remove completed jobs and update running ones
      const stillRunning = updatedJobs.filter(
        job => job.status.status === 'processing'
      );
      
      setRunningImports(stillRunning);
      
      // If any jobs completed, refresh history
      if (stillRunning.length < runningImports.length) {
        loadImportHistory();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [runningImports, loadImportHistory]);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setValidationResult(null);
      setUploadedFilePath(null);
      setError(null);
      setSuccess(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      setIsUploading(true);
      setError(null);
      setUploadProgress(0);

      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 100);

      const response = await apiClient.uploadImportFile(selectedFile);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      setUploadedFilePath(response.file_path);
      setSuccess('File uploaded successfully');

      // Auto-validate after upload
      setTimeout(() => handleValidate(response.file_path), 500);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleValidate = async (filePath?: string) => {
    const pathToValidate = filePath || uploadedFilePath;
    if (!pathToValidate) return;

    try {
      setIsValidating(true);
      setError(null);

      const result = await apiClient.validateImport(pathToValidate);
      setValidationResult(result);

      if (!result.valid) {
        setError(result.error || 'Validation failed');
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Validation failed');
    } finally {
      setIsValidating(false);
    }
  };

  const handleStartImport = async () => {
    if (!uploadedFilePath || !validationResult?.valid) return;

    try {
      setError(null);
      
      const response = await apiClient.executeImport(uploadedFilePath);
      
      // Add to running imports
      const newJob: ImportJob = {
        id: response.import_id,
        status: {
          import_id: response.import_id,
          status: 'processing',
          stage: 'initializing',
          total_records: validationResult.total_records || 0,
          processed_records: 0,
          imported_records: 0,
          failed_records: 0,
          progress_percentage: 0,
          current_operation: 'Starting import...',
          errors: []
        },
        startTime: new Date()
      };

      setRunningImports(prev => [...prev, newJob]);
      setSuccess('Import started successfully');
      setActiveTab('running');

      // Reset upload state
      setSelectedFile(null);
      setUploadedFilePath(null);
      setValidationResult(null);
      setUploadProgress(0);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start import');
    }
  };

  const handleCancelImport = async (importId: string) => {
    try {
      await apiClient.cancelImport(importId);
      setRunningImports(prev => prev.filter(job => job.id !== importId));
      setSuccess('Import cancelled');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel import');
    }
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  const getStatusBadge = (status: string, success?: boolean) => {
    if (status === 'processing') {
      return <Badge variant="default" className="bg-blue-500">Processing</Badge>;
    }
    if (status === 'completed') {
      return success ? 
        <Badge variant="default" className="bg-green-500">Completed</Badge> :
        <Badge variant="destructive">Failed</Badge>;
    }
    if (status === 'failed') {
      return <Badge variant="destructive">Failed</Badge>;
    }
    return <Badge variant="secondary">{status}</Badge>;
  };

  return (
    <div className={cn("space-y-6", className)}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Import Manager</h2>
          <p className="text-muted-foreground">
            Upload and import Etilize CSV files into the product database
          </p>
        </div>
        <Button onClick={loadImportHistory} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Alert Messages */}
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

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="upload" className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Upload
          </TabsTrigger>
          <TabsTrigger value="running" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Running ({runningImports.length})
          </TabsTrigger>
          <TabsTrigger value="history" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            History
          </TabsTrigger>
        </TabsList>

        {/* Upload Tab */}
        <TabsContent value="upload" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Upload CSV File</CardTitle>
              <CardDescription>
                Select an Etilize CSV file to upload and import into the product database
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="file-upload">Choose file</Label>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".csv,.txt"
                  onChange={handleFileSelect}
                  disabled={isUploading}
                />
                {selectedFile && (
                  <p className="text-sm text-muted-foreground">
                    Selected: {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                  </p>
                )}
              </div>

              {isUploading && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>Uploading...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <Progress value={uploadProgress} />
                </div>
              )}

              <Button 
                onClick={handleUpload}
                disabled={!selectedFile || isUploading}
                className="w-full"
              >
                {isUploading ? (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4 mr-2" />
                    Upload File
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Validation Results */}
          {uploadedFilePath && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  File Validation
                  {isValidating && <RefreshCw className="h-4 w-4 animate-spin" />}
                </CardTitle>
                <CardDescription>
                  Validation results for the uploaded file
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {validationResult ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      {validationResult.valid ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-500" />
                      )}
                      <span className="font-medium">
                        {validationResult.valid ? 'File is valid' : 'File has errors'}
                      </span>
                    </div>

                    {validationResult.valid && (
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">Total Records:</span>
                          <span className="ml-2 font-medium">{validationResult.total_records}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Columns:</span>
                          <span className="ml-2 font-medium">{validationResult.available_columns?.length}</span>
                        </div>
                      </div>
                    )}

                    {validationResult.available_columns && (
                      <div>
                        <Label className="text-sm font-medium">Available Columns</Label>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {validationResult.available_columns.map((col, idx) => (
                            <Badge key={idx} variant="secondary" className="text-xs">
                              {col}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {validationResult.valid && (
                      <Button onClick={handleStartImport} className="w-full">
                        <Play className="h-4 w-4 mr-2" />
                        Start Import
                      </Button>
                    )}
                  </div>
                ) : (
                  <Button 
                    onClick={() => handleValidate()}
                    disabled={isValidating}
                    variant="outline"
                  >
                    {isValidating ? 'Validating...' : 'Validate File'}
                  </Button>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Running Imports Tab */}
        <TabsContent value="running" className="space-y-4">
          {runningImports.length === 0 ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <div className="text-center">
                  <Clock className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-muted-foreground">No imports currently running</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            runningImports.map((job) => (
              <Card key={job.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">Import {job.id.slice(0, 8)}</CardTitle>
                      <CardDescription>
                        Started {job.startTime.toLocaleTimeString()}
                      </CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      {getStatusBadge(job.status.status)}
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleCancelImport(job.id)}
                      >
                        <Pause className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span>{job.status.current_operation}</span>
                      <span>{job.status.progress_percentage.toFixed(1)}%</span>
                    </div>
                    <Progress value={job.status.progress_percentage} />
                  </div>

                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Total:</span>
                      <span className="ml-2 font-medium">{job.status.total_records}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Imported:</span>
                      <span className="ml-2 font-medium text-green-600">{job.status.imported_records}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Failed:</span>
                      <span className="ml-2 font-medium text-red-600">{job.status.failed_records}</span>
                    </div>
                  </div>

                  {job.status.errors.length > 0 && (
                    <Alert variant="destructive">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        {job.status.errors.slice(0, 3).join('; ')}
                        {job.status.errors.length > 3 && ` (and ${job.status.errors.length - 3} more)`}
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-4">
          {isLoadingHistory ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <RefreshCw className="h-6 w-6 animate-spin" />
              </CardContent>
            </Card>
          ) : importHistory.length === 0 ? (
            <Card>
              <CardContent className="flex items-center justify-center py-8">
                <div className="text-center">
                  <FileText className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
                  <p className="text-muted-foreground">No import history available</p>
                </div>
              </CardContent>
            </Card>
          ) : (
            importHistory.map((item) => (
              <Card key={item.import_id}>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h4 className="font-medium">Import {item.import_id.slice(0, 8)}</h4>
                      <p className="text-sm text-muted-foreground">
                        Batch #{item.batch_id}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {getStatusBadge('completed', item.success)}
                      <span className="text-sm text-muted-foreground">
                        {formatDuration(item.duration_seconds)}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Total:</span>
                      <span className="ml-2 font-medium">{item.total_records}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Imported:</span>
                      <span className="ml-2 font-medium text-green-600">{item.imported_records}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Failed:</span>
                      <span className="ml-2 font-medium text-red-600">{item.failed_records}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Success Rate:</span>
                      <span className="ml-2 font-medium">
                        {((item.imported_records / item.total_records) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {item.errors.length > 0 && (
                    <Alert variant="destructive" className="mt-4">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        {item.errors.slice(0, 2).join('; ')}
                        {item.errors.length > 2 && ` (and ${item.errors.length - 2} more)`}
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}