import { motion } from 'framer-motion';
import { Box, Columns2, Footprints, Gem, Shirt, Wind } from 'lucide-react';

import type { SavedItem } from '../../../types/item';

type FeedClosetFoldersProps = {
  folders: string[];
  items: SavedItem[];
  onSelectFolder: (folder: string) => void;
};

const HANGING_FOLDERS = ['outer', 'top', 'outerwear', 'tops'];
const DRAWER_FOLDERS = ['bottom', 'bottoms', 'pants'];
const SIDE_FOLDERS = ['shoes', 'accessories', 'jewelry'];
const KNOWN_FOLDERS = [...HANGING_FOLDERS, ...DRAWER_FOLDERS, ...SIDE_FOLDERS];

function inGroup(folder: string, group: string[]) {
  return group.includes(folder.toLowerCase());
}

function FolderCount({ folder, items }: { folder: string; items: SavedItem[] }) {
  return (
    <div className="absolute top-3 right-3 text-[10px] font-bold opacity-30 group-hover/item:opacity-100">
      {items.filter((item) => item.category === folder).length}
    </div>
  );
}

export function FeedClosetFolders({ folders, items, onSelectFolder }: FeedClosetFoldersProps) {
  const hangingFolders = folders.filter((folder) => inGroup(folder, HANGING_FOLDERS));
  const drawerFolders = folders.filter((folder) => inGroup(folder, DRAWER_FOLDERS));
  const sideFolders = folders.filter((folder) => inGroup(folder, SIDE_FOLDERS));
  const otherFolders = folders.filter((folder) => !inGroup(folder, KNOWN_FOLDERS));

  return (
    <div className="col-span-full grid grid-cols-1 lg:grid-cols-4 gap-6 bg-zinc-50/50 p-6 sm:p-10 rounded-[3rem] border border-zinc-200 shadow-sm relative overflow-hidden">
      <div className="absolute top-0 right-0 w-64 h-64 bg-zinc-200/20 rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl pointer-events-none" />

      <div className="lg:col-span-3 space-y-6">
        <div className="relative min-h-[320px] bg-white border border-zinc-200 rounded-[2.5rem] p-8 overflow-hidden group/hanging shadow-sm">
          <div className="absolute top-10 left-8 right-8 h-1 bg-zinc-200 rounded-full shadow-inner" />
          <div className="absolute top-4 left-8 text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em] flex items-center gap-2">
            <Shirt className="w-3 h-3" /> Hanging Section
          </div>
          <div className="flex flex-wrap gap-6 pt-12">
            {hangingFolders.map((folder) => (
              <motion.div
                layout
                key={`folder-${folder}`}
                onClick={() => onSelectFolder(folder)}
                className="group/item relative flex w-32 sm:w-40 aspect-[3/4] flex-col items-center justify-center p-4 bg-white border border-zinc-100 rounded-xl shadow-sm transition-all duration-500 cursor-pointer hover:shadow-xl hover:-translate-y-2 hover:border-black"
              >
                <FolderCount folder={folder} items={items} />
                <div className="w-8 h-8 rounded-full bg-zinc-50 flex items-center justify-center mb-4 group-hover/item:bg-black group-hover/item:text-white transition-colors">
                  {['outer', 'outerwear'].includes(folder.toLowerCase()) ? (
                    <Wind className="w-4 h-4" />
                  ) : (
                    <Shirt className="w-4 h-4" />
                  )}
                </div>
                <h3 className="text-[11px] font-bold text-foreground uppercase tracking-widest text-center px-2">{folder}</h3>
              </motion.div>
            ))}
          </div>
        </div>

        <div className="relative min-h-[180px] bg-zinc-100 border border-zinc-200 rounded-[2.5rem] p-8 shadow-inner overflow-hidden">
          <div className="absolute top-4 left-8 text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em]">Lower Drawer</div>
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 w-12 h-1 bg-white rounded-full shadow-sm" />
          <div className="flex flex-wrap gap-6 justify-center">
            {drawerFolders.map((folder) => (
              <motion.div
                layout
                key={`folder-${folder}`}
                onClick={() => onSelectFolder(folder)}
                className="group/item relative flex w-32 sm:w-40 aspect-square flex-col items-center justify-center p-4 bg-white border border-zinc-100 rounded-xl shadow-sm transition-all duration-500 cursor-pointer hover:shadow-xl hover:-translate-y-1 hover:border-black"
              >
                <FolderCount folder={folder} items={items} />
                <div className="w-8 h-8 rounded-full bg-zinc-50 flex items-center justify-center mb-4 group-hover/item:bg-black group-hover/item:text-white transition-colors">
                  <Columns2 className="w-4 h-4" />
                </div>
                <h3 className="text-[11px] font-bold text-foreground uppercase tracking-widest text-center px-2">{folder}</h3>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      <div className="lg:col-span-1 relative bg-zinc-200/40 border border-zinc-200 rounded-[2.5rem] p-8 flex flex-col gap-6 shadow-sm overflow-hidden">
        <div className="absolute top-4 left-8 text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em] flex items-center gap-2">
          <Box className="w-3 h-3" /> Side Storage
        </div>
        <div className="flex flex-col gap-6 pt-8 items-center">
          {sideFolders.map((folder) => (
            <motion.div
              layout
              key={`folder-${folder}`}
              onClick={() => onSelectFolder(folder)}
              className="group/item relative flex w-full max-w-[160px] aspect-square flex-col items-center justify-center p-4 bg-white border border-zinc-100 rounded-xl shadow-sm transition-all duration-500 cursor-pointer hover:shadow-xl hover:scale-105 hover:border-black"
            >
              <FolderCount folder={folder} items={items} />
              <div className="w-8 h-8 rounded-full bg-zinc-50 flex items-center justify-center mb-4 group-hover/item:bg-black group-hover/item:text-white transition-colors">
                {folder.toLowerCase() === 'shoes' ? (
                  <Footprints className="w-4 h-4" />
                ) : (
                  <Gem className="w-4 h-4" />
                )}
              </div>
              <h3 className="text-[11px] font-bold text-foreground uppercase tracking-widest text-center px-2">{folder}</h3>
            </motion.div>
          ))}
        </div>
      </div>

      {otherFolders.length > 0 && (
        <div className="col-span-full pt-8 border-t border-zinc-200/50 mt-4">
          <h4 className="text-[10px] font-bold text-zinc-400 uppercase tracking-[0.2em] mb-6 px-2">Other Collections</h4>
          <div className="flex flex-wrap gap-4">
            {otherFolders.map((folder) => (
              <motion.div
                layout
                key={`folder-${folder}`}
                onClick={() => onSelectFolder(folder)}
                className="group/item relative flex px-6 py-3 items-center justify-center bg-white border border-zinc-200 rounded-full shadow-sm transition-all duration-300 cursor-pointer hover:bg-black hover:text-white hover:border-black"
              >
                <span className="text-[10px] font-bold uppercase tracking-widest">{folder}</span>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
