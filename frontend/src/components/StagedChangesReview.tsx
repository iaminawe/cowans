import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  GitCompare,
  Check,
  X,
  Eye,
  Filter,
  Search,
  AlertTriangle,
  FileText,
  Package,
  TrendingUp,
  TrendingDown,
  Edit,
  Trash2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  History,
  GitMerge,
  Clock
} from 'lucide-react';
import { apiClient } from '@/lib/api';

interface StagedChangesReviewProps {
  onChangesApproved?: () => void;
  className?: string;
}

// Using StagedChange from API types

interface LocalStagedChange {
  id: string;
  source: string;
  productId: string;
  sku: string;
  title: string;
  changeType: 'create' | 'update' | 'delete' | 'price' | 'inventory' | 'metadata';
  stagedAt: string;
  stagedBy: string;
  status: 'pending' | 'approved' | 'rejected';
  fields: FieldChange[];
  conflicts?: ChangeConflict[];
  priority: 'low' | 'medium' | 'high';
}

interface FieldChange {
  field: string;
  oldValue: any;
  newValue: any;
  dataType: 'string' | 'number' | 'boolean' | 'array' | 'object';
  impact: 'low' | 'medium' | 'high';
}

interface ChangeConflict {
  field: string;
  localValue: any;
  remoteValue: any;
  stagedValue: any;
  resolution?: 'local' | 'remote' | 'staged' | 'custom';
  customValue?: any;
}

interface FilterOptions {
  changeTypes: string[];
  sources: string[];
  priorities: string[];
  statuses: string[];
  searchQuery: string;
}

export function StagedChangesReview({ onChangesApproved, className }: StagedChangesReviewProps) {
  const [activeTab, setActiveTab] = useState<'pending' | 'approved' | 'rejected' | 'conflicts'>('pending');
  const [stagedChanges, setStagedChanges] = useState<LocalStagedChange[]>([]);
  const [selectedChanges, setSelectedChanges] = useState<Set<string>>(new Set());
  const [expandedChanges, setExpandedChanges] = useState<Set<string>>(new Set());
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({
    changeTypes: [],
    sources: [],
    priorities: [],
    statuses: ['pending'],
    searchQuery: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadStagedChanges();
  }, [filterOptions]);

  const loadStagedChanges = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.getStagedChanges(filterOptions);
      // Convert API StagedChange to LocalStagedChange
      const localChanges: LocalStagedChange[] = response.changes.map(change => ({
        id: change.id || '',
        source: change.source || 'system',
        productId: change.product_id || '',
        sku: (change as any).sku || '',
        title: (change as any).title || '',
        changeType: change.change_type as any || 'update',
        stagedAt: change.created_at || new Date().toISOString(),
        stagedBy: (change as any).created_by || 'system',
        status: change.status as 'pending' | 'approved' | 'rejected' || 'pending',
        fields: change.field_changes ? Object.entries(change.field_changes).map(([field, values]) => ({
          field,
          oldValue: values.old_value,
          newValue: values.new_value,
          dataType: typeof values.new_value as any,
          impact: 'medium' as const
        })) : [],
        conflicts: [],
        priority: 'medium' as const
      }));
      setStagedChanges(localChanges);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load staged changes');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectChange = (changeId: string, selected: boolean) => {
    setSelectedChanges(prev => {
      const newSet = new Set(prev);
      if (selected) {
        newSet.add(changeId);
      } else {
        newSet.delete(changeId);
      }
      return newSet;
    });
  };

  const handleSelectAll = (selected: boolean) => {
    if (selected) {
      const pendingChanges = stagedChanges
        .filter(c => c.status === 'pending')
        .map(c => c.id);
      setSelectedChanges(new Set(pendingChanges));
    } else {
      setSelectedChanges(new Set());
    }
  };

  const handleToggleExpanded = (changeId: string) => {
    setExpandedChanges(prev => {
      const newSet = new Set(prev);
      if (newSet.has(changeId)) {
        newSet.delete(changeId);
      } else {
        newSet.add(changeId);
      }
      return newSet;
    });
  };

  const handleApproveChanges = async (changeIds?: string[]) => {
    const ids = changeIds || Array.from(selectedChanges);
    if (ids.length === 0) return;

    try {
      await apiClient.approveChanges(ids);
      setSuccess(`${ids.length} changes approved`);
      setSelectedChanges(new Set());
      loadStagedChanges();
      
      if (onChangesApproved) {
        onChangesApproved();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve changes');
    }
  };

  const handleRejectChanges = async (changeIds?: string[]) => {
    const ids = changeIds || Array.from(selectedChanges);
    if (ids.length === 0) return;

    try {
      await apiClient.rejectChanges(ids);
      setSuccess(`${ids.length} changes rejected`);
      setSelectedChanges(new Set());
      loadStagedChanges();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject changes');
    }
  };

  const handleResolveConflict = async (changeId: string, resolution: any) => {
    try {
      await apiClient.resolveConflict(changeId, resolution);
      setSuccess('Conflict resolved');
      loadStagedChanges();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resolve conflict');
    }
  };

  const getChangeTypeIcon = (type: string) => {
    switch (type) {
      case 'create':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'update':
        return <Edit className="h-4 w-4 text-blue-500" />;
      case 'delete':
        return <Trash2 className="h-4 w-4 text-red-500" />;
      case 'price':
        return <TrendingDown className="h-4 w-4 text-orange-500" />;
      case 'inventory':
        return <Package className="h-4 w-4 text-purple-500" />;
      case 'metadata':
        return <FileText className="h-4 w-4 text-gray-500" />;
      default:
        return null;
    }
  };

  const getImpactBadge = (impact: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive'> = {
      low: 'secondary',
      medium: 'default',
      high: 'destructive'
    };
    return <Badge variant={variants[impact] || 'secondary'}>{impact} impact</Badge>;
  };

  const getPriorityBadge = (priority: string) => {
    const variants: Record<string, 'default' | 'secondary' | 'destructive'> = {
      low: 'secondary',
      medium: 'default',
      high: 'destructive'
    };
    return <Badge variant={variants[priority] || 'secondary'}>{priority}</Badge>;
  };

  const formatFieldValue = (value: any, dataType: string): string => {
    if (value === null || value === undefined) return 'Empty';
    
    switch (dataType) {
      case 'array':
        return `[${Array.isArray(value) ? value.length : 0} items]`;
      case 'object':
        return JSON.stringify(value, null, 2);
      case 'boolean':
        return value ? 'Yes' : 'No';
      case 'number':
        return value.toString();
      default:
        return value.toString();
    }
  };

  const renderFieldChange = (field: FieldChange) => (
    <div key={field.field} className="grid grid-cols-3 gap-4 py-2 border-b last:border-0">
      <div>
        <p className="text-sm font-medium">{field.field}</p>
        {getImpactBadge(field.impact)}
      </div>
      <div className="text-sm">
        <p className="text-muted-foreground">Old:</p>
        <code className="text-xs bg-muted px-1 py-0.5 rounded">
          {formatFieldValue(field.oldValue, field.dataType)}
        </code>
      </div>
      <div className="text-sm">
        <p className="text-muted-foreground">New:</p>
        <code className="text-xs bg-muted px-1 py-0.5 rounded">
          {formatFieldValue(field.newValue, field.dataType)}
        </code>
      </div>
    </div>
  );

  const renderConflict = (conflict: ChangeConflict, changeId: string) => (
    <div key={conflict.field} className="space-y-2 p-3 border rounded-lg">
      <p className="font-medium text-sm">{conflict.field} Conflict</p>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <Button
          variant={conflict.resolution === 'local' ? 'default' : 'outline'}
          size="sm"
          onClick={() => handleResolveConflict(changeId, { field: conflict.field, resolution: 'local' })}
        >
          Local: {formatFieldValue(conflict.localValue, 'string')}
        </Button>
        <Button
          variant={conflict.resolution === 'remote' ? 'default' : 'outline'}
          size="sm"
          onClick={() => handleResolveConflict(changeId, { field: conflict.field, resolution: 'remote' })}
        >
          Remote: {formatFieldValue(conflict.remoteValue, 'string')}
        </Button>
        <Button
          variant={conflict.resolution === 'staged' ? 'default' : 'outline'}
          size="sm"
          onClick={() => handleResolveConflict(changeId, { field: conflict.field, resolution: 'staged' })}
        >
          Staged: {formatFieldValue(conflict.stagedValue, 'string')}
        </Button>
      </div>
    </div>
  );

  const pendingChanges = stagedChanges?.filter(c => c.status === 'pending') || [];
  const approvedChanges = stagedChanges?.filter(c => c.status === 'approved') || [];
  const rejectedChanges = stagedChanges?.filter(c => c.status === 'rejected') || [];
  const conflictedChanges = stagedChanges?.filter(c => c.conflicts && c.conflicts.length > 0) || [];

  return (
    <div className={cn("space-y-6", className)}>
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {success && (
        <Alert>
          <Check className="h-4 w-4" />
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pendingChanges.length}</div>
            <p className="text-xs text-muted-foreground">Awaiting decision</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Approved</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{approvedChanges.length}</div>
            <p className="text-xs text-muted-foreground">Ready to sync</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Rejected</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{rejectedChanges.length}</div>
            <p className="text-xs text-muted-foreground">Will not sync</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Conflicts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">{conflictedChanges.length}</div>
            <p className="text-xs text-muted-foreground">Need resolution</p>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="pending" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Pending ({pendingChanges.length})
          </TabsTrigger>
          <TabsTrigger value="approved" className="flex items-center gap-2">
            <Check className="h-4 w-4" />
            Approved ({approvedChanges.length})
          </TabsTrigger>
          <TabsTrigger value="rejected" className="flex items-center gap-2">
            <X className="h-4 w-4" />
            Rejected ({rejectedChanges.length})
          </TabsTrigger>
          <TabsTrigger value="conflicts" className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />
            Conflicts ({conflictedChanges.length})
          </TabsTrigger>
        </TabsList>

        {/* Pending Tab */}
        <TabsContent value="pending" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Pending Changes</CardTitle>
                  <CardDescription>Review and approve or reject staged changes</CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={selectedChanges.size === pendingChanges.length && pendingChanges.length > 0}
                    onCheckedChange={handleSelectAll}
                  />
                  <Label className="text-sm font-normal">Select All</Label>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {/* Action Bar */}
              {selectedChanges.size > 0 && (
                <div className="mb-4 p-3 bg-muted rounded-lg flex items-center justify-between">
                  <p className="text-sm">{selectedChanges.size} changes selected</p>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRejectChanges()}
                    >
                      <X className="h-4 w-4 mr-1" />
                      Reject
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleApproveChanges()}
                    >
                      <Check className="h-4 w-4 mr-1" />
                      Approve
                    </Button>
                  </div>
                </div>
              )}

              {/* Changes List */}
              <ScrollArea className="h-[600px]">
                <div className="space-y-4">
                  {pendingChanges.map((change) => (
                    <Card key={change.id} className="overflow-hidden">
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-3">
                            <Checkbox
                              checked={selectedChanges.has(change.id)}
                              onCheckedChange={(checked) => handleSelectChange(change.id, checked as boolean)}
                            />
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                {getChangeTypeIcon(change.changeType)}
                                <h4 className="font-medium">{change.title}</h4>
                                <Badge variant="outline">{change.changeType}</Badge>
                                {getPriorityBadge(change.priority)}
                              </div>
                              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                <span>SKU: {change.sku}</span>
                                <span>Source: {change.source}</span>
                                <span>Staged: {new Date(change.stagedAt).toLocaleString()}</span>
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleToggleExpanded(change.id)}
                            >
                              {expandedChanges.has(change.id) ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRejectChanges([change.id])}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleApproveChanges([change.id])}
                            >
                              <Check className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      </CardHeader>
                      
                      {expandedChanges.has(change.id) && (
                        <CardContent className="pt-0">
                          <div className="space-y-4">
                            <div>
                              <h5 className="text-sm font-medium mb-2">Field Changes</h5>
                              {change.fields.map(renderFieldChange)}
                            </div>
                            
                            {change.conflicts && change.conflicts.length > 0 && (
                              <div>
                                <h5 className="text-sm font-medium mb-2 text-orange-600">Conflicts</h5>
                                <div className="space-y-2">
                                  {change.conflicts.map(conflict => renderConflict(conflict, change.id))}
                                </div>
                              </div>
                            )}
                          </div>
                        </CardContent>
                      )}
                    </Card>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Approved Tab */}
        <TabsContent value="approved" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Approved Changes</CardTitle>
              <CardDescription>Changes ready to be synced to Shopify</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[600px]">
                <div className="space-y-4">
                  {approvedChanges.map((change) => (
                    <div key={change.id} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {getChangeTypeIcon(change.changeType)}
                          <div>
                            <p className="font-medium">{change.title}</p>
                            <p className="text-sm text-muted-foreground">
                              SKU: {change.sku} • Approved: {new Date(change.stagedAt).toLocaleString()}
                            </p>
                          </div>
                        </div>
                        <Badge variant="outline" className="bg-green-50">Approved</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Rejected Tab */}
        <TabsContent value="rejected" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Rejected Changes</CardTitle>
              <CardDescription>Changes that will not be synced</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[600px]">
                <div className="space-y-4">
                  {rejectedChanges.map((change) => (
                    <div key={change.id} className="p-4 border rounded-lg opacity-60">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {getChangeTypeIcon(change.changeType)}
                          <div>
                            <p className="font-medium">{change.title}</p>
                            <p className="text-sm text-muted-foreground">
                              SKU: {change.sku} • Rejected: {new Date(change.stagedAt).toLocaleString()}
                            </p>
                          </div>
                        </div>
                        <Badge variant="outline" className="bg-red-50">Rejected</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Conflicts Tab */}
        <TabsContent value="conflicts" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Conflicted Changes</CardTitle>
              <CardDescription>Changes that need manual resolution</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[600px]">
                <div className="space-y-4">
                  {conflictedChanges.map((change) => (
                    <Card key={change.id} className="border-orange-200">
                      <CardHeader>
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="h-4 w-4 text-orange-500" />
                          <h4 className="font-medium">{change.title}</h4>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          SKU: {change.sku} • {change.conflicts?.length || 0} conflicts
                        </p>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-3">
                          {change.conflicts?.map(conflict => renderConflict(conflict, change.id))}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}