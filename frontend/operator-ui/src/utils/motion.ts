// Utility for handling reduced motion preferences
export const getMotionPreference = () => {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

// Motion variants that respect user preferences
export const motionVariants = {
  // Fade in/out
  fade: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
    transition: { duration: getMotionPreference() ? 0 : 0.28, ease: [0.2, 0.8, 0.2, 1] }
  },
  
  // Slide up
  slideUp: {
    initial: { opacity: 0, y: getMotionPreference() ? 0 : 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: getMotionPreference() ? 0 : -20 },
    transition: { duration: getMotionPreference() ? 0 : 0.28, ease: [0.2, 0.8, 0.2, 1] }
  },
  
  // Slide from right
  slideRight: {
    initial: { opacity: 0, x: getMotionPreference() ? 0 : '100%' },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: getMotionPreference() ? 0 : '100%' },
    transition: { type: 'spring', damping: 30, stiffness: 300, duration: getMotionPreference() ? 0 : undefined }
  },
  
  // Scale
  scale: {
    initial: { opacity: 0, scale: getMotionPreference() ? 1 : 0.8 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: getMotionPreference() ? 1 : 0.8 },
    transition: { duration: getMotionPreference() ? 0 : 0.28, ease: [0.2, 0.8, 0.2, 1] }
  }
};

// Hover animations that respect motion preferences
export const hoverVariants = {
  scale: getMotionPreference() ? {} : { scale: 1.02 },
  tap: getMotionPreference() ? {} : { scale: 0.98 }
};
