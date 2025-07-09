import React, { useState, useEffect } from 'react';
import { cn } from "@/lib/utils";
import { shopifyApi } from '@/lib/shopifyApi';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Image, Upload, CheckCircle2, AlertCircle } from 'lucide-react';

interface LocalIcon {
  id: string;
  category_id: string;
  category_name: string;
  file_path: string;
  thumbnail_url?: string;
  created_at: string;
  metadata?: any;
}

interface IconSyncDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  collectionId: string;
  collectionName: string;
  onSync: (collectionId: string, iconId: string) => Promise<void>;
}

export function IconSyncDialog({
  open,
  onOpenChange,
  collectionId,
  collectionName,
  onSync
}: IconSyncDialogProps) {
  const [localIcons, setLocalIcons] = useState<LocalIcon[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [selectedIcon, setSelectedIcon] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      loadLocalIcons();
    }
  }, [open, collectionName]);

  const loadLocalIcons = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // This would typically call an API to get icons matching the collection name
      // For now, we'll use a mock implementation
      const response = await fetch('/api/icons/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          query: collectionName,
          filters: {
            synced: false
          }
        })
      });

      if (!response.ok) {
        throw new Error('Failed to load local icons');
      }

      const data = await response.json();
      setLocalIcons(data.icons || []);
      
    } catch (error: any) {
      console.error('Error loading local icons:', error);
      setError(error.message || 'Failed to load icons');
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    if (!selectedIcon) return;

    try {
      setSyncing(true);
      setError(null);
      
      await onSync(collectionId, selectedIcon);
      
      // Close dialog on success
      onOpenChange(false);
      
    } catch (error: any) {
      console.error('Error syncing icon:', error);
      setError(error.message || 'Failed to sync icon');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Sync Icon to Shopify Collection</DialogTitle>
          <DialogDescription>
            Select a locally generated icon to upload to "{collectionName}"
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : localIcons.length === 0 ? (
            <div className="text-center py-8">
              <Image className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                No matching icons found. Try generating one first.
              </p>
            </div>
          ) : (
            <ScrollArea className="h-[300px] pr-4">
              <div className="space-y-2">
                {localIcons.map((icon) => (
                  <div
                    key={icon.id}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
                      selectedIcon === icon.id
                        ? "border-primary bg-primary/5"
                        : "hover:bg-gray-100 dark:hover:bg-gray-800"
                    )}
                    onClick={() => setSelectedIcon(icon.id)}
                  >
                    {icon.thumbnail_url ? (
                      <img
                        src={icon.thumbnail_url}
                        alt={icon.category_name}
                        className="w-12 h-12 rounded object-cover border"
                      />
                    ) : (
                      <div className="w-12 h-12 rounded border bg-muted flex items-center justify-center">
                        <Image className="h-6 w-6 text-muted-foreground" />
                      </div>
                    )}
                    
                    <div className="flex-1">
                      <div className="font-medium">{icon.category_name}</div>
                      <div className="text-sm text-muted-foreground">
                        Created {new Date(icon.created_at).toLocaleDateString()}
                      </div>
                    </div>

                    {selectedIcon === icon.id && (
                      <CheckCircle2 className="h-5 w-5 text-primary" />
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={syncing}>
            Cancel
          </Button>
          <Button
            onClick={handleSync}
            disabled={!selectedIcon || syncing}
            className="flex items-center gap-2"
          >
            {syncing ? (
              <>
                <Upload className="h-4 w-4 animate-pulse" />
                Syncing...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Sync to Shopify
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}