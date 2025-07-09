import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Image, Sparkles, Loader2, Grid3X3, List, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Collection {
  id: string;
  title: string;
  handle: string;
  products_count: number;
  image_url?: string;
  has_icon: boolean;
}

interface BulkIconPreviewProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  collections: Collection[];
  style: string;
  colorScheme: string;
  onGenerate: () => void;
  isGenerating: boolean;
}

export function BulkIconPreview({
  open,
  onOpenChange,
  collections,
  style,
  colorScheme,
  onGenerate,
  isGenerating
}: BulkIconPreviewProps) {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  
  const collectionsWithIcons = collections.filter(c => c.has_icon);
  const collectionsWithoutIcons = collections.filter(c => !c.has_icon);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>Bulk Icon Generation Preview</DialogTitle>
          <DialogDescription>
            Review the collections that will have icons generated
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4">
          {/* Summary */}
          <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
            <div className="flex items-center gap-4">
              <div>
                <p className="text-sm font-medium">Total Collections</p>
                <p className="text-2xl font-bold">{collections.length}</p>
              </div>
              <div className="h-8 w-px bg-border" />
              <div>
                <p className="text-sm font-medium">New Icons</p>
                <p className="text-2xl font-bold text-green-600">{collectionsWithoutIcons.length}</p>
              </div>
              <div className="h-8 w-px bg-border" />
              <div>
                <p className="text-sm font-medium">Replacements</p>
                <p className="text-2xl font-bold text-yellow-600">{collectionsWithIcons.length}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">Style: {style}</Badge>
              <Badge variant="secondary">Colors: {colorScheme}</Badge>
            </div>
          </div>

          {/* View Toggle */}
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">Selected Collections</h3>
            <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as 'grid' | 'list')}>
              <TabsList>
                <TabsTrigger value="grid">
                  <Grid3X3 className="w-4 h-4 mr-2" />
                  Grid
                </TabsTrigger>
                <TabsTrigger value="list">
                  <List className="w-4 h-4 mr-2" />
                  List
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {/* Collections Display */}
          <ScrollArea className="h-[400px] border rounded-lg">
            <div className="p-4">
              {viewMode === 'grid' ? (
                <div className="grid grid-cols-3 md:grid-cols-4 gap-4">
                  {collections.map((collection) => (
                    <div
                      key={collection.id}
                      className="group relative aspect-square rounded-lg border overflow-hidden hover:shadow-md transition-shadow"
                    >
                      <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-primary/5" />
                      {collection.image_url ? (
                        <img
                          src={collection.image_url}
                          alt={collection.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Image className="w-12 h-12 text-muted-foreground" />
                        </div>
                      )}
                      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2">
                        <p className="text-white text-xs font-medium truncate">{collection.title}</p>
                        <div className="flex items-center gap-1 mt-1">
                          <Badge variant={collection.has_icon ? "secondary" : "default"} className="text-xs">
                            {collection.has_icon ? "Replace" : "New"}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {collections.map((collection) => (
                    <div
                      key={collection.id}
                      className="flex items-center gap-3 p-3 rounded-lg border hover:bg-accent transition-colors"
                    >
                      <div className="w-12 h-12 rounded overflow-hidden bg-muted flex-shrink-0">
                        {collection.image_url ? (
                          <img
                            src={collection.image_url}
                            alt={collection.title}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <Image className="w-6 h-6 text-muted-foreground" />
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{collection.title}</p>
                        <p className="text-sm text-muted-foreground truncate">{collection.handle}</p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Badge variant="outline" className="text-xs">
                          {collection.products_count} products
                        </Badge>
                        {collection.has_icon && (
                          <Badge variant="secondary" className="text-xs">
                            <CheckCircle2 className="w-3 h-3 mr-1" />
                            Has Icon
                          </Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Generation Settings Summary */}
          <div className="p-3 bg-muted/50 rounded-lg text-sm">
            <p className="font-medium mb-1">Generation Settings:</p>
            <ul className="space-y-1 text-muted-foreground">
              <li>• Style: {style}</li>
              <li>• Color Scheme: {colorScheme}</li>
              <li>• Estimated time: ~{Math.ceil(collections.length * 0.5)} minutes</li>
            </ul>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={onGenerate} disabled={isGenerating}>
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Starting Generation...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Generate {collections.length} Icons
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}