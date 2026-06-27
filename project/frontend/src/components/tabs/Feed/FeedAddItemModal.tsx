import { AnimatePresence, motion } from 'framer-motion';
import { Loader2, Plus, X } from 'lucide-react';
import type { FormEvent } from 'react';

type FeedAddItemModalProps = {
  isOpen: boolean;
  isPending: boolean;
  newUrl: string;
  sessionId: string;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  onNewUrlChange: (url: string) => void;
  onSessionIdChange: (sessionId: string) => void;
};

export function FeedAddItemModal({
  isOpen,
  isPending,
  newUrl,
  sessionId,
  onClose,
  onSubmit,
  onNewUrlChange,
  onSessionIdChange,
}: FeedAddItemModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            key="add-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            key="add-popup"
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div className="w-full max-w-md rounded-2xl sm:rounded-3xl bg-background p-6 sm:p-8 shadow-2xl border border-border">
              <div className="flex items-center justify-between mb-6 sm:mb-8">
                <h3 className="editorial-heading text-xl sm:text-2xl text-foreground">추가하기</h3>
                <button
                  onClick={onClose}
                  className="w-8 h-8 sm:w-9 sm:h-9 flex items-center justify-center rounded-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  <X className="w-4 h-4 sm:w-5 sm:h-5" />
                </button>
              </div>

              <form onSubmit={onSubmit} className="space-y-4 sm:space-y-5">
                <div>
                  <label className="block text-[10px] sm:text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 sm:mb-2">
                    URL 혹은 상품이름
                  </label>
                  <input
                    type="url"
                    placeholder="https://..."
                    value={newUrl}
                    onChange={(e) => onNewUrlChange(e.target.value)}
                    className="w-full h-10 sm:h-12 px-3 sm:px-4 bg-muted rounded-xl text-xs sm:text-sm font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-black/20"
                  />
                </div>
                <div>
                  <label className="block text-[10px] sm:text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5 sm:mb-2">
                    Session ID (Optional)
                  </label>
                  <input
                    type="password"
                    placeholder="Session ID"
                    value={sessionId}
                    onChange={(e) => onSessionIdChange(e.target.value)}
                    className="w-full h-10 sm:h-12 px-3 sm:px-4 bg-muted rounded-xl text-xs sm:text-sm font-medium placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-black/20"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isPending || !newUrl}
                  className="w-full h-10 sm:h-12 flex items-center justify-center rounded-full bg-black text-white text-xs sm:text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
                >
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.span
                      key={isPending ? 'pending' : 'idle'}
                      initial={{ opacity: 0, y: 3 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -3 }}
                      transition={{ duration: 0.12, ease: 'easeOut' }}
                      className="flex items-center gap-2"
                    >
                      {isPending ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Adding...
                        </>
                      ) : (
                        <>
                          <Plus className="w-4 h-4" />
                          Add Item
                        </>
                      )}
                    </motion.span>
                  </AnimatePresence>
                </button>
              </form>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
