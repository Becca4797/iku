import { supabase } from "/js/supabaseClient.js";

export async function signUp({ firstName, lastName, email, phone, password }) {
  return supabase.auth.signUp({
    email,
    password,
    options: {
      // Copied into your profiles table by the database trigger
      data: { first_name: firstName, last_name: lastName, phone },
    },
  });
}

export async function logIn({ email, password }) {
  return supabase.auth.signInWithPassword({ email, password });
}

export async function logOut() {
  return supabase.auth.signOut();
}