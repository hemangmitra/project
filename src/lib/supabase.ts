import { createClient } from '@supabase/supabase-js'
import { Database } from '../types/database'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('Missing Supabase environment variables:', {
    url: !!supabaseUrl,
    key: !!supabaseAnonKey
  })
  throw new Error('Missing Supabase environment variables. Please check your .env file.')
}

export const supabase = createClient<Database>(supabaseUrl, supabaseAnonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    flowType: 'pkce'
  }
})

// Add connection test
supabase.auth.getSession().then(({ data, error }) => {
  if (error) {
    console.error('Supabase connection error:', error)
  } else {
    console.log('Supabase connected successfully')
  }
}).catch(err => {
  console.error('Failed to connect to Supabase:', err)
})