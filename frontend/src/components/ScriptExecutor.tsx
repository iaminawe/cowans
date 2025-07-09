import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { StatusIndicator } from './StatusIndicator';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Checkbox } from './ui/checkbox';
import { Label } from './ui/label';
import { FileText, Play, Settings, Clock, ChevronRight } from 'lucide-react';

interface ScriptParameter {
  name: string;
  type: 'text' | 'boolean' | 'select' | 'file';
  label: string;
  required?: boolean;
  options?: string[];
  default?: string | boolean;
  description?: string;
}

interface Script {
  id: string;
  name: string;
  description: string;
  category: 'download' | 'processing' | 'upload' | 'cleanup' | 'debug';
  parameters: ScriptParameter[];
  estimatedTime?: number; // in seconds
}

interface ScriptExecutorProps {
  onExecute: (scriptId: string, parameters: Record<string, any>) => void;
  isExecuting?: boolean;
  currentScript?: string;
  progress?: number;
  logs?: string[];
}

const AVAILABLE_SCRIPTS: Script[] = [
  {
    id: 'ftp_download',
    name: 'FTP Download',
    description: 'Download product data from Etilize FTP server',
    category: 'download',
    estimatedTime: 180,
    parameters: []
  },
  {
    id: 'filter_products',
    name: 'Filter Products',
    description: 'Filter products against reference data',
    category: 'processing',
    estimatedTime: 120,
    parameters: [
      {
        name: 'inputFile',
        type: 'file',
        label: 'Input CSV File',
        required: true,
        description: 'CSV file containing products to filter'
      },
      {
        name: 'referenceFile',
        type: 'file',
        label: 'Reference File',
        required: true,
        description: 'Xorosoft reference file for matching'
      },
      {
        name: 'debug',
        type: 'boolean',
        label: 'Debug Mode',
        default: false,
        description: 'Enable detailed debug output'
      }
    ]
  },
  {
    id: 'create_metafields',
    name: 'Create Metafields',
    description: 'Generate Shopify metafields from product data',
    category: 'processing',
    estimatedTime: 300,
    parameters: [
      {
        name: 'inputFile',
        type: 'file',
        label: 'Input CSV File',
        required: true,
        description: 'CSV file to process'
      }
    ]
  },
  {
    id: 'shopify_upload',
    name: 'Upload to Shopify',
    description: 'Upload products to Shopify store',
    category: 'upload',
    estimatedTime: 600,
    parameters: [
      {
        name: 'csvFile',
        type: 'file',
        label: 'CSV File',
        required: true,
        description: 'CSV file containing products to upload'
      },
      {
        name: 'skipImages',
        type: 'boolean',
        label: 'Skip Images',
        default: false,
        description: 'Skip image uploads for faster processing'
      },
      {
        name: 'batchSize',
        type: 'text',
        label: 'Batch Size',
        default: '10',
        description: 'Number of products to process per batch'
      }
    ]
  },
  {
    id: 'cleanup_duplicates',
    name: 'Cleanup Duplicate Images',
    description: 'Remove duplicate images from Shopify products',
    category: 'cleanup',
    estimatedTime: 300,
    parameters: [
      {
        name: 'dryRun',
        type: 'boolean',
        label: 'Dry Run',
        default: true,
        description: 'Simulate cleanup without making changes'
      }
    ]
  },
  {
    id: 'full_import',
    name: 'Full Import Workflow',
    description: 'Run complete import workflow from FTP to Shopify',
    category: 'processing',
    estimatedTime: 1200,
    parameters: [
      {
        name: 'skipDownload',
        type: 'boolean',
        label: 'Skip Download',
        default: false,
        description: 'Skip FTP download stage'
      },
      {
        name: 'skipFilter',
        type: 'boolean',
        label: 'Skip Filter',
        default: false,
        description: 'Skip product filtering stage'
      },
      {
        name: 'skipMetafields',
        type: 'boolean',
        label: 'Skip Metafields',
        default: false,
        description: 'Skip metafields creation stage'
      },
      {
        name: 'skipUpload',
        type: 'boolean',
        label: 'Skip Upload',
        default: false,
        description: 'Skip Shopify upload stage'
      }
    ]
  }
];

export function ScriptExecutor({ 
  onExecute, 
  isExecuting = false, 
  currentScript,
  progress = 0,
  logs = []
}: ScriptExecutorProps) {
  const [selectedScript, setSelectedScript] = useState<Script | null>(null);
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [category, setCategory] = useState<string>('all');

  useEffect(() => {
    if (selectedScript) {
      const defaultParams: Record<string, any> = {};
      selectedScript.parameters.forEach(param => {
        if (param.default !== undefined) {
          defaultParams[param.name] = param.default;
        }
      });
      setParameters(defaultParams);
    }
  }, [selectedScript]);

  const filteredScripts = AVAILABLE_SCRIPTS.filter(script => 
    category === 'all' || script.category === category
  );

  const handleParameterChange = (name: string, value: any) => {
    setParameters(prev => ({ ...prev, [name]: value }));
  };

  const handleExecute = () => {
    if (selectedScript) {
      onExecute(selectedScript.id, parameters);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  return (
    <div className="space-y-6">
      {/* Script Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Script Execution
          </CardTitle>
          <CardDescription>
            Select and configure scripts for your product integration workflow
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Category Filter */}
          <div className="flex flex-wrap gap-2 mb-6">
            {['all', 'download', 'processing', 'upload', 'cleanup', 'debug'].map((cat) => (
              <Badge
                key={cat}
                variant={category === cat ? "default" : "secondary"}
                className={cn(
                  "cursor-pointer transition-all hover:scale-105",
                  category === cat ? "shadow-md" : "hover:bg-secondary/80"
                )}
                onClick={() => setCategory(cat)}
              >
                {cat.charAt(0).toUpperCase() + cat.slice(1)}
              </Badge>
            ))}
          </div>

          {/* Script Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredScripts.map((script) => {
              const getCategoryColor = (category: string) => {
                switch (category) {
                  case 'download': return 'border-l-blue-500';
                  case 'processing': return 'border-l-yellow-500';
                  case 'upload': return 'border-l-green-500';
                  case 'cleanup': return 'border-l-red-500';
                  case 'debug': return 'border-l-purple-500';
                  default: return 'border-l-gray-500';
                }
              };
              
              const getCategoryIcon = (category: string) => {
                switch (category) {
                  case 'download': return '⬇️';
                  case 'processing': return '⚙️';
                  case 'upload': return '⬆️';
                  case 'cleanup': return '🧹';
                  case 'debug': return '🔍';
                  default: return '📄';
                }
              };
              
              return (
                <Card
                  key={script.id}
                  className={cn(
                    "cursor-pointer transition-all duration-200 hover:shadow-lg border-l-4",
                    getCategoryColor(script.category),
                    selectedScript?.id === script.id
                      ? "ring-2 ring-primary shadow-md"
                      : "hover:ring-1 hover:ring-primary/50",
                    isExecuting && "opacity-50 cursor-not-allowed"
                  )}
                  onClick={() => !isExecuting && setSelectedScript(script)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="font-medium flex items-center gap-2">
                        <span>{getCategoryIcon(script.category)}</span>
                        {script.name}
                      </div>
                      {selectedScript?.id === script.id && (
                        <ChevronRight className="h-4 w-4 text-primary" />
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">
                      {script.description}
                    </p>
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-xs">
                        {script.category}
                      </Badge>
                      {script.estimatedTime && (
                        <div className="flex items-center gap-1 text-xs text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          {formatTime(script.estimatedTime)}
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Parameter Form */}
      {selectedScript && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              {selectedScript.name} Configuration
            </CardTitle>
            <CardDescription>
              Configure parameters for {selectedScript.name.toLowerCase()}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {selectedScript.parameters.length === 0 ? (
              <div className="text-center py-8">
                <Settings className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-sm text-muted-foreground">
                  This script has no configurable parameters.
                </p>
              </div>
            ) : (
              <div className="space-y-6">
                {selectedScript.parameters.map((param) => (
                  <div key={param.name} className="space-y-2">
                    {param.type === 'text' && (
                      <div className="space-y-2">
                        <Label>{param.label}{param.required && <span className="text-red-500 ml-1">*</span>}</Label>
                        <Input
                          value={parameters[param.name] || ''}
                          onChange={(e) => handleParameterChange(param.name, e.target.value)}
                          placeholder={`Enter ${param.label.toLowerCase()}...`}
                        />
                        {param.description && (
                          <p className="text-xs text-muted-foreground">{param.description}</p>
                        )}
                      </div>
                    )}
                    
                    {param.type === 'boolean' && (
                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id={param.name}
                          checked={parameters[param.name] || false}
                          onCheckedChange={(checked) => handleParameterChange(param.name, checked)}
                        />
                        <Label htmlFor={param.name} className="text-sm font-medium">
                          {param.label}
                        </Label>
                        {param.description && (
                          <p className="text-xs text-muted-foreground ml-2">
                            {param.description}
                          </p>
                        )}
                      </div>
                    )}
                    
                    {param.type === 'file' && (
                      <div className="space-y-2">
                        <Label>{param.label}{param.required && <span className="text-red-500 ml-1">*</span>}</Label>
                        <Input
                          type="file"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            handleParameterChange(param.name, file?.name || '');
                          }}
                          placeholder="Select file..."
                        />
                        {param.description && (
                          <p className="text-xs text-muted-foreground">{param.description}</p>
                        )}
                      </div>
                    )}
                    
                    {param.type === 'select' && (
                      <div className="space-y-2">
                        <Label>{param.label}{param.required && <span className="text-red-500 ml-1">*</span>}</Label>
                        <Select
                          value={parameters[param.name] || ''}
                          onValueChange={(value) => handleParameterChange(param.name, value)}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="Select an option..." />
                          </SelectTrigger>
                          <SelectContent>
                            {param.options?.map((option) => (
                              <SelectItem key={option} value={option}>
                                {option}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {param.description && (
                          <p className="text-xs text-muted-foreground">
                            {param.description}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
            
            <div className="mt-8 flex items-center justify-between">
              <Button
                onClick={handleExecute}
                disabled={isExecuting}
                size="lg"
                className="min-w-[150px]"
              >
                <Play className="mr-2 h-4 w-4" />
                {isExecuting ? 'Executing...' : 'Execute Script'}
              </Button>
              
              {selectedScript.estimatedTime && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Clock className="h-4 w-4" />
                  <span>Estimated time: {formatTime(selectedScript.estimatedTime)}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Progress Indicator */}
      {isExecuting && currentScript && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Play className="h-5 w-5 animate-pulse" />
                  Execution in Progress
                </CardTitle>
                <CardDescription>Running: {currentScript}</CardDescription>
              </div>
              <StatusIndicator status="running" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Progress 
                value={progress} 
                showValue={true}
                className="w-full"
              />
              
              {/* Recent Logs */}
              {logs.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm font-medium">Recent Output:</Label>
                  <Card className="bg-black/95 text-green-400">
                    <CardContent className="p-4">
                      <div className="text-xs font-mono max-h-32 overflow-y-auto space-y-1">
                        {logs.slice(-5).map((log, index) => (
                          <div key={index} className="whitespace-pre-wrap animate-in fade-in duration-300">
                            <span className="text-gray-500">[{new Date().toLocaleTimeString()}]</span> {log}
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}