import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { 
  Users, UserPlus, Search, Filter, Edit, Trash2, Shield, ShieldOff,
  Eye, MoreHorizontal, AlertTriangle, CheckCircle, XCircle, Clock,
  UserCheck, UserX, Mail, Calendar, Activity
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { cn } from '@/lib/utils';

interface User {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
  is_admin: boolean;
  supabase_id?: string;
  last_login?: string;
  created_at: string;
  updated_at?: string;
  job_count?: number;
  recent_activity?: Array<{
    script_name: string;
    status: string;
    created_at: string;
  }>;
}

interface UserFormData {
  email: string;
  first_name: string;
  last_name: string;
  password?: string;
  is_admin: boolean;
  is_active: boolean;
}

interface UserFilters {
  search: string;
  is_active?: boolean;
  is_admin?: boolean;
  sort_by: string;
  sort_order: 'asc' | 'desc';
}

interface PaginationInfo {
  page: number;
  limit: number;
  total: number;
  pages: number;
}

export function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // Modal states
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [viewModalOpen, setViewModalOpen] = useState(false);
  
  // Form states
  const [formData, setFormData] = useState<UserFormData>({
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    is_admin: false,
    is_active: true
  });
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [bulkSelectedUsers, setBulkSelectedUsers] = useState<Set<number>>(new Set());
  
  // Filter and pagination states
  const [filters, setFilters] = useState<UserFilters>({
    search: '',
    is_active: undefined,
    is_admin: undefined,
    sort_by: 'created_at',
    sort_order: 'desc'
  });
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    limit: 10,
    total: 0,
    pages: 0
  });

  useEffect(() => {
    loadUsers();
  }, [filters, pagination.page, pagination.limit]);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params = new URLSearchParams({
        page: pagination.page.toString(),
        limit: pagination.limit.toString(),
        search: filters.search,
        sort_by: filters.sort_by,
        sort_order: filters.sort_order
      });
      
      if (filters.is_active !== undefined) {
        params.append('is_active', filters.is_active.toString());
      }
      if (filters.is_admin !== undefined) {
        params.append('is_admin', filters.is_admin.toString());
      }
      
      const response = await apiClient.get<{users: User[], pagination: PaginationInfo}>(`/admin/users?${params}`);
      setUsers(response.users || []);
      setPagination(response.pagination);
      
    } catch (err: any) {
      console.error('Failed to load users:', err);
      setError(err.response?.data?.message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    try {
      setError(null);
      
      if (!formData.email || !formData.password) {
        setError('Email and password are required');
        return;
      }
      
      await apiClient.post('/admin/users', formData);
      setSuccess('User created successfully');
      setCreateModalOpen(false);
      resetForm();
      loadUsers();
      
    } catch (err: any) {
      console.error('Failed to create user:', err);
      setError(err.response?.data?.message || 'Failed to create user');
    }
  };

  const handleUpdateUser = async () => {
    if (!selectedUser) return;
    
    try {
      setError(null);
      
      const updateData = {
        first_name: formData.first_name,
        last_name: formData.last_name,
        is_admin: formData.is_admin,
        is_active: formData.is_active
      };
      
      await apiClient.put(`/admin/users/${selectedUser.id}`, updateData);
      setSuccess('User updated successfully');
      setEditModalOpen(false);
      resetForm();
      loadUsers();
      
    } catch (err: any) {
      console.error('Failed to update user:', err);
      setError(err.response?.data?.message || 'Failed to update user');
    }
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) return;
    
    try {
      setError(null);
      
      await apiClient.delete(`/admin/users/${selectedUser.id}`);
      setSuccess('User deleted successfully');
      setDeleteModalOpen(false);
      setSelectedUser(null);
      loadUsers();
      
    } catch (err: any) {
      console.error('Failed to delete user:', err);
      setError(err.response?.data?.message || 'Failed to delete user');
    }
  };

  const handleToggleAdmin = async (user: User) => {
    try {
      setError(null);
      
      await apiClient.put(`/admin/users/${user.id}`, {
        is_admin: !user.is_admin
      });
      
      setSuccess(`User ${user.is_admin ? 'removed from' : 'granted'} admin privileges`);
      loadUsers();
      
    } catch (err: any) {
      console.error('Failed to toggle admin status:', err);
      setError(err.response?.data?.message || 'Failed to update admin status');
    }
  };

  const handleToggleActive = async (user: User) => {
    try {
      setError(null);
      
      await apiClient.put(`/admin/users/${user.id}`, {
        is_active: !user.is_active
      });
      
      setSuccess(`User ${user.is_active ? 'deactivated' : 'activated'}`);
      loadUsers();
      
    } catch (err: any) {
      console.error('Failed to toggle user status:', err);
      setError(err.response?.data?.message || 'Failed to update user status');
    }
  };

  const handleBulkAction = async (action: 'activate' | 'deactivate' | 'make_admin' | 'remove_admin' | 'delete') => {
    if (bulkSelectedUsers.size === 0) return;
    
    try {
      setError(null);
      const userIds = Array.from(bulkSelectedUsers);
      
      switch (action) {
        case 'activate':
        case 'deactivate':
          await Promise.all(userIds.map(id => 
            apiClient.put(`/admin/users/${id}`, { is_active: action === 'activate' })
          ));
          setSuccess(`${userIds.length} users ${action}d`);
          break;
          
        case 'make_admin':
        case 'remove_admin':
          await Promise.all(userIds.map(id => 
            apiClient.put(`/admin/users/${id}`, { is_admin: action === 'make_admin' })
          ));
          setSuccess(`${userIds.length} users ${action === 'make_admin' ? 'granted' : 'removed'} admin privileges`);
          break;
          
        case 'delete':
          await Promise.all(userIds.map(id => apiClient.delete(`/admin/users/${id}`)));
          setSuccess(`${userIds.length} users deleted`);
          break;
      }
      
      setBulkSelectedUsers(new Set());
      loadUsers();
      
    } catch (err: any) {
      console.error('Bulk action failed:', err);
      setError(`Bulk action failed: ${err.response?.data?.message || 'Unknown error'}`);
    }
  };

  const openEditModal = (user: User) => {
    setSelectedUser(user);
    setFormData({
      email: user.email,
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      is_admin: user.is_admin,
      is_active: user.is_active
    });
    setEditModalOpen(true);
  };

  const openViewModal = (user: User) => {
    setSelectedUser(user);
    setViewModalOpen(true);
  };

  const openDeleteModal = (user: User) => {
    setSelectedUser(user);
    setDeleteModalOpen(true);
  };

  const resetForm = () => {
    setFormData({
      email: '',
      first_name: '',
      last_name: '',
      password: '',
      is_admin: false,
      is_active: true
    });
    setSelectedUser(null);
  };

  const handleBulkSelect = (userId: number, selected: boolean) => {
    const newSelection = new Set(bulkSelectedUsers);
    if (selected) {
      newSelection.add(userId);
    } else {
      newSelection.delete(userId);
    }
    setBulkSelectedUsers(newSelection);
  };

  const handleSelectAll = (selected: boolean) => {
    if (selected) {
      setBulkSelectedUsers(new Set(users.map(u => u.id)));
    } else {
      setBulkSelectedUsers(new Set());
    }
  };

  const getStatusIcon = (user: User) => {
    if (!user.is_active) return <UserX className="h-4 w-4 text-red-500" />;
    if (user.is_admin) return <Shield className="h-4 w-4 text-blue-500" />;
    return <UserCheck className="h-4 w-4 text-green-500" />;
  };

  const formatLastLogin = (lastLogin?: string) => {
    if (!lastLogin) return 'Never';
    const date = new Date(lastLogin);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString();
  };

  if (loading && users.length === 0) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">User Management</h2>
          <p className="text-muted-foreground">
            Manage user accounts, permissions, and access controls
          </p>
        </div>
        <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
          <DialogTrigger asChild>
            <Button className="flex items-center gap-2">
              <UserPlus className="h-4 w-4" />
              Add User
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Create New User</DialogTitle>
              <DialogDescription>
                Add a new user to the system with appropriate permissions.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="email" className="text-right">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  className="col-span-3"
                  placeholder="user@company.com"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="password" className="text-right">
                  Password
                </Label>
                <Input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                  className="col-span-3"
                  placeholder="Secure password"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="first_name" className="text-right">
                  First Name
                </Label>
                <Input
                  id="first_name"
                  value={formData.first_name}
                  onChange={(e) => setFormData(prev => ({ ...prev, first_name: e.target.value }))}
                  className="col-span-3"
                  placeholder="John"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="last_name" className="text-right">
                  Last Name
                </Label>
                <Input
                  id="last_name"
                  value={formData.last_name}
                  onChange={(e) => setFormData(prev => ({ ...prev, last_name: e.target.value }))}
                  className="col-span-3"
                  placeholder="Doe"
                />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label className="text-right">Permissions</Label>
                <div className="col-span-3 space-y-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="is_active"
                      checked={formData.is_active}
                      onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_active: checked as boolean }))}
                    />
                    <Label htmlFor="is_active">Active user</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="is_admin"
                      checked={formData.is_admin}
                      onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_admin: checked as boolean }))}
                    />
                    <Label htmlFor="is_admin">Administrator privileges</Label>
                  </div>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => { setCreateModalOpen(false); resetForm(); }}>
                Cancel
              </Button>
              <Button onClick={handleCreateUser}>Create User</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Alerts */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      
      {success && (
        <Alert>
          <CheckCircle className="h-4 w-4" />
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {/* Filters and Search */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Search & Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search by email or name..."
                  value={filters.search}
                  onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                  className="pl-9"
                />
              </div>
            </div>
            
            <Select
              value={filters.is_active === undefined ? 'all' : filters.is_active.toString()}
              onValueChange={(value) => setFilters(prev => ({
                ...prev,
                is_active: value === 'all' ? undefined : value === 'true'
              }))}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Users</SelectItem>
                <SelectItem value="true">Active</SelectItem>
                <SelectItem value="false">Inactive</SelectItem>
              </SelectContent>
            </Select>
            
            <Select
              value={filters.is_admin === undefined ? 'all' : filters.is_admin.toString()}
              onValueChange={(value) => setFilters(prev => ({
                ...prev,
                is_admin: value === 'all' ? undefined : value === 'true'
              }))}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                <SelectItem value="true">Admins</SelectItem>
                <SelectItem value="false">Users</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      {bulkSelectedUsers.size > 0 && (
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                {bulkSelectedUsers.size} user{bulkSelectedUsers.size > 1 ? 's' : ''} selected
              </span>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkAction('activate')}
                >
                  <UserCheck className="h-4 w-4 mr-1" />
                  Activate
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkAction('deactivate')}
                >
                  <UserX className="h-4 w-4 mr-1" />
                  Deactivate
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkAction('make_admin')}
                >
                  <Shield className="h-4 w-4 mr-1" />
                  Make Admin
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkAction('remove_admin')}
                >
                  <ShieldOff className="h-4 w-4 mr-1" />
                  Remove Admin
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => handleBulkAction('delete')}
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  Delete
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Users Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Users ({pagination.total})</CardTitle>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                Page {pagination.page} of {pagination.pages}
              </span>
              <Select
                value={pagination.limit.toString()}
                onValueChange={(value) => setPagination(prev => ({ ...prev, limit: parseInt(value), page: 1 }))}
              >
                <SelectTrigger className="w-[80px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">
                  <Checkbox
                    checked={users.length > 0 && bulkSelectedUsers.size === users.length}
                    onCheckedChange={handleSelectAll}
                  />
                </TableHead>
                <TableHead>User</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Last Login</TableHead>
                <TableHead>Jobs</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell>
                    <Checkbox
                      checked={bulkSelectedUsers.has(user.id)}
                      onCheckedChange={(checked) => handleBulkSelect(user.id, checked as boolean)}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      {getStatusIcon(user)}
                      <div>
                        <div className="font-medium">{user.email}</div>
                        <div className="text-sm text-muted-foreground">
                          {user.first_name || user.last_name 
                            ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                            : 'No name set'}
                        </div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.is_active ? 'default' : 'secondary'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {user.is_admin && (
                        <Badge variant="outline" className="flex items-center gap-1">
                          <Shield className="h-3 w-3" />
                          Admin
                        </Badge>
                      )}
                      {!user.is_admin && (
                        <span className="text-sm text-muted-foreground">User</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2 text-sm">
                      <Clock className="h-3 w-3 text-muted-foreground" />
                      {formatLastLogin(user.last_login)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2 text-sm">
                      <Activity className="h-3 w-3 text-muted-foreground" />
                      {user.job_count || 0}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openViewModal(user)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openEditModal(user)}
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleToggleAdmin(user)}
                        title={user.is_admin ? 'Remove admin privileges' : 'Grant admin privileges'}
                      >
                        {user.is_admin ? (
                          <ShieldOff className="h-4 w-4 text-orange-500" />
                        ) : (
                          <Shield className="h-4 w-4 text-blue-500" />
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openDeleteModal(user)}
                        className="text-red-500 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          
          {/* Pagination */}
          <div className="flex items-center justify-between pt-4">
            <div className="text-sm text-muted-foreground">
              Showing {((pagination.page - 1) * pagination.limit) + 1} to {Math.min(pagination.page * pagination.limit, pagination.total)} of {pagination.total} users
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setPagination(prev => ({ ...prev, page: Math.max(1, prev.page - 1) }))}
                disabled={pagination.page <= 1}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setPagination(prev => ({ ...prev, page: Math.min(prev.pages, prev.page + 1) }))}
                disabled={pagination.page >= pagination.pages}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Edit User Modal */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Edit User</DialogTitle>
            <DialogDescription>
              Update user information and permissions.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="edit_email" className="text-right">
                Email
              </Label>
              <Input
                id="edit_email"
                value={formData.email}
                disabled
                className="col-span-3 bg-muted"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="edit_first_name" className="text-right">
                First Name
              </Label>
              <Input
                id="edit_first_name"
                value={formData.first_name}
                onChange={(e) => setFormData(prev => ({ ...prev, first_name: e.target.value }))}
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="edit_last_name" className="text-right">
                Last Name
              </Label>
              <Input
                id="edit_last_name"
                value={formData.last_name}
                onChange={(e) => setFormData(prev => ({ ...prev, last_name: e.target.value }))}
                className="col-span-3"
              />
            </div>
            <div className="grid grid-cols-4 items-center gap-4">
              <Label className="text-right">Permissions</Label>
              <div className="col-span-3 space-y-2">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="edit_is_active"
                    checked={formData.is_active}
                    onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_active: checked as boolean }))}
                  />
                  <Label htmlFor="edit_is_active">Active user</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="edit_is_admin"
                    checked={formData.is_admin}
                    onCheckedChange={(checked) => setFormData(prev => ({ ...prev, is_admin: checked as boolean }))}
                  />
                  <Label htmlFor="edit_is_admin">Administrator privileges</Label>
                </div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setEditModalOpen(false); resetForm(); }}>
              Cancel
            </Button>
            <Button onClick={handleUpdateUser}>Update User</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View User Modal */}
      <Dialog open={viewModalOpen} onOpenChange={setViewModalOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>User Details</DialogTitle>
            <DialogDescription>
              Detailed information about {selectedUser?.email}
            </DialogDescription>
          </DialogHeader>
          {selectedUser && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm font-medium">Email</Label>
                  <p className="text-sm text-muted-foreground">{selectedUser.email}</p>
                </div>
                <div>
                  <Label className="text-sm font-medium">Full Name</Label>
                  <p className="text-sm text-muted-foreground">
                    {selectedUser.first_name || selectedUser.last_name 
                      ? `${selectedUser.first_name || ''} ${selectedUser.last_name || ''}`.trim()
                      : 'Not set'}
                  </p>
                </div>
                <div>
                  <Label className="text-sm font-medium">Status</Label>
                  <Badge variant={selectedUser.is_active ? 'default' : 'secondary'}>
                    {selectedUser.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
                <div>
                  <Label className="text-sm font-medium">Role</Label>
                  <Badge variant={selectedUser.is_admin ? 'default' : 'outline'}>
                    {selectedUser.is_admin ? 'Administrator' : 'User'}
                  </Badge>
                </div>
                <div>
                  <Label className="text-sm font-medium">Last Login</Label>
                  <p className="text-sm text-muted-foreground">
                    {formatLastLogin(selectedUser.last_login)}
                  </p>
                </div>
                <div>
                  <Label className="text-sm font-medium">Jobs Run</Label>
                  <p className="text-sm text-muted-foreground">
                    {selectedUser.job_count || 0} total
                  </p>
                </div>
                <div>
                  <Label className="text-sm font-medium">Created</Label>
                  <p className="text-sm text-muted-foreground">
                    {new Date(selectedUser.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div>
                  <Label className="text-sm font-medium">Last Updated</Label>
                  <p className="text-sm text-muted-foreground">
                    {selectedUser.updated_at 
                      ? new Date(selectedUser.updated_at).toLocaleDateString()
                      : 'Never'}
                  </p>
                </div>
              </div>
              
              {selectedUser.recent_activity && selectedUser.recent_activity.length > 0 && (
                <div>
                  <Label className="text-sm font-medium mb-2 block">Recent Activity</Label>
                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {selectedUser.recent_activity.map((activity, index) => (
                      <div key={index} className="flex items-center justify-between text-sm p-2 bg-muted rounded">
                        <span>{activity.script_name}</span>
                        <div className="flex items-center gap-2">
                          <Badge variant={activity.status === 'completed' ? 'default' : 'secondary'}>
                            {activity.status}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {new Date(activity.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewModalOpen(false)}>
              Close
            </Button>
            <Button onClick={() => {
              setViewModalOpen(false);
              if (selectedUser) openEditModal(selectedUser);
            }}>
              Edit User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Modal */}
      <Dialog open={deleteModalOpen} onOpenChange={setDeleteModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete User</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete {selectedUser?.email}? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteUser}>
              Delete User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}