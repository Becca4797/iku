import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm";
import { SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY } from "/js/config.js";

// Always keep the user logged in: the session is saved on the device
// until they log out or the app's storage is cleared.
export const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: {
    storage: window.localStorage,
    persistSession: true,
    autoRefreshToken: true,
  },
});