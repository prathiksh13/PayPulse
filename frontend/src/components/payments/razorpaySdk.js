let loadPromise = null;

/**
 * Loads the Razorpay Checkout SDK once (https://checkout.razorpay.com/v1/checkout.js).
 * Resolves with the window.Razorpay constructor, or rejects so the UI can handle
 * CDN/initialization failures cleanly.
 */
export function loadRazorpaySdk() {
  if (window.Razorpay) return Promise.resolve(window.Razorpay);
  if (loadPromise) return loadPromise;

  loadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.async = true;
    script.onload = () => {
      if (window.Razorpay) {
        resolve(window.Razorpay);
      } else {
        loadPromise = null;
        reject(new Error('Razorpay SDK loaded but failed to initialize'));
      }
    };
    script.onerror = () => {
      loadPromise = null;
      reject(new Error('Could not load the Razorpay Checkout SDK'));
    };
    document.head.appendChild(script);
  });

  return loadPromise;
}