import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { User, LoginRequest, RegisterRequest } from '../types'
import { authApi } from '../services/supabaseApi'
import { supabase } from '../lib/supabase'
import toast from 'react-hot-toast'

interface AuthState {
  user: User | null
  isLoading: boolean
  login: (credentials: LoginRequest) => Promise<void>
  register: (userData: RegisterRequest) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
  updateUser: (user: User) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isLoading: true,

      login: async (credentials: LoginRequest) => {
        try {
          set({ isLoading: true })
          await authApi.login(credentials)
          
          // Get user profile after login
          const user = await authApi.getProfile()
          
          set({ 
            user,
            isLoading: false 
          })
          
          toast.success('Login successful!')
        } catch (error: any) {
          set({ isLoading: false })
          toast.error(error.message || 'Login failed')
          throw error
        }
      },

      register: async (userData: RegisterRequest) => {
        try {
          set({ isLoading: true })
          await authApi.register(userData)
          set({ isLoading: false })
          toast.success('Registration successful! Please check your email to verify your account.')
        } catch (error: any) {
          set({ isLoading: false })
          toast.error(error.message || 'Registration failed')
          throw error
        }
      },

      logout: async () => {
        try {
          await authApi.logout()
          set({ user: null, isLoading: false })
          toast.success('Logged out successfully')
        } catch (error: any) {
          set({ user: null, isLoading: false })
          toast.error(error.message || 'Logout failed')
        }
      },

      checkAuth: async () => {
        try {
          set({ isLoading: true })
          
          const { data: { session }, error } = await supabase.auth.getSession()
          
          if (error) {
            console.error('Session error:', error)
            set({ user: null, isLoading: false })
            return
          }
          
          if (session?.user) {
            try {
              const user = await authApi.getProfile()
              set({ user, isLoading: false })
            } catch (profileError) {
              console.error('Profile error:', profileError)
              // If profile doesn't exist, sign out
              await supabase.auth.signOut()
              set({ user: null, isLoading: false })
            }
          } else {
            set({ user: null, isLoading: false })
          }
        } catch (error) {
          console.error('Auth check error:', error)
          set({ user: null, isLoading: false })
        }
      },

      updateUser: (user: User) => {
        set({ user })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ 
        user: state.user 
      }),
    }
  )
)

// Listen for auth changes
supabase.auth.onAuthStateChange(async (event, session) => {
  console.log('Auth state changed:', event, session?.user?.id)
  
  if (event === 'SIGNED_IN' && session) {
    try {
      const user = await authApi.getProfile()
      useAuthStore.setState({ user, isLoading: false })
    } catch (error) {
      console.error('Error getting profile after sign in:', error)
      useAuthStore.setState({ user: null, isLoading: false })
    }
  } else if (event === 'SIGNED_OUT') {
    useAuthStore.setState({ user: null, isLoading: false })
  } else if (event === 'TOKEN_REFRESHED') {
    // Token refreshed, user should still be valid
    const currentUser = useAuthStore.getState().user
    if (currentUser) {
      useAuthStore.setState({ isLoading: false })
    }
  }
})