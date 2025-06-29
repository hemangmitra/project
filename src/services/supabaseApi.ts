import { supabase } from '../lib/supabase'
import { 
  User, 
  Task, 
  TaskCreate, 
  TaskUpdate, 
  LoginRequest, 
  RegisterRequest,
  AuditLog,
  SystemStats,
  PaginatedResponse
} from '../types'

export const authApi = {
  login: async (credentials: LoginRequest) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email: credentials.email,
      password: credentials.password,
    })
    
    if (error) {
      console.error('Login error:', error)
      throw new Error(error.message)
    }
    return data
  },

  register: async (userData: RegisterRequest) => {
    const { data, error } = await supabase.auth.signUp({
      email: userData.email,
      password: userData.password,
      options: {
        data: {
          username: userData.username,
        },
      },
    })
    
    if (error) {
      console.error('Registration error:', error)
      throw new Error(error.message)
    }
    return data
  },

  getProfile: async (): Promise<User> => {
    const { data: { user }, error: userError } = await supabase.auth.getUser()
    
    if (userError) {
      console.error('Get user error:', userError)
      throw new Error('Failed to get user')
    }
    
    if (!user) {
      throw new Error('Not authenticated')
    }

    const { data: profile, error } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', user.id)
      .single()

    if (error) {
      console.error('Get profile error:', error)
      throw new Error('Failed to get profile: ' + error.message)
    }
    
    if (!profile) {
      throw new Error('Profile not found')
    }
    
    return {
      id: profile.id,
      email: user.email!,
      username: profile.username,
      role: profile.role,
      is_active: profile.is_active,
      created_at: profile.created_at,
      updated_at: profile.updated_at,
    }
  },

  updateProfile: async (userData: Partial<User>): Promise<User> => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) throw new Error('Not authenticated')

    // Update email in auth if provided
    if (userData.email && userData.email !== user.email) {
      const { error: emailError } = await supabase.auth.updateUser({
        email: userData.email,
      })
      if (emailError) throw new Error(emailError.message)
    }

    // Update profile
    const { data: profile, error } = await supabase
      .from('profiles')
      .update({
        username: userData.username,
      })
      .eq('id', user.id)
      .select()
      .single()

    if (error) throw new Error(error.message)

    return {
      id: profile.id,
      email: userData.email || user.email!,
      username: profile.username,
      role: profile.role,
      is_active: profile.is_active,
      created_at: profile.created_at,
      updated_at: profile.updated_at,
    }
  },

  logout: async () => {
    const { error } = await supabase.auth.signOut()
    if (error) throw new Error(error.message)
  },
}

export const tasksApi = {
  getTasks: async (params?: {
    page?: number
    size?: number
    status?: string
    priority?: string
    search?: string
  }): Promise<PaginatedResponse<Task>> => {
    const page = params?.page || 1
    const size = params?.size || 10
    const from = (page - 1) * size
    const to = from + size - 1

    let query = supabase
      .from('tasks')
      .select('*', { count: 'exact' })
      .eq('is_deleted', false)
      .order('created_at', { ascending: false })

    if (params?.status) {
      query = query.eq('status', params.status)
    }

    if (params?.priority) {
      query = query.eq('priority', params.priority)
    }

    if (params?.search) {
      query = query.or(`title.ilike.%${params.search}%,description.ilike.%${params.search}%`)
    }

    const { data, error, count } = await query.range(from, to)

    if (error) throw new Error(error.message)

    return {
      data: data || [],
      total: count || 0,
      page,
      size,
    }
  },

  getTask: async (id: number): Promise<Task> => {
    const { data, error } = await supabase
      .from('tasks')
      .select('*')
      .eq('id', id)
      .eq('is_deleted', false)
      .single()

    if (error) throw new Error(error.message)
    return data
  },

  createTask: async (taskData: TaskCreate): Promise<Task> => {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) throw new Error('Not authenticated')

    const { data, error } = await supabase
      .from('tasks')
      .insert({
        ...taskData,
        created_by: user.id,
      })
      .select()
      .single()

    if (error) throw new Error(error.message)
    return data
  },

  updateTask: async (id: number, taskData: TaskUpdate): Promise<Task> => {
    const { data, error } = await supabase
      .from('tasks')
      .update(taskData)
      .eq('id', id)
      .select()
      .single()

    if (error) throw new Error(error.message)
    return data
  },

  deleteTask: async (id: number): Promise<void> => {
    const { error } = await supabase
      .from('tasks')
      .update({ is_deleted: true })
      .eq('id', id)

    if (error) throw new Error(error.message)
  },
}

export const adminApi = {
  getSystemStats: async (): Promise<SystemStats> => {
    try {
      // Get total users
      const { count: totalUsers } = await supabase
        .from('profiles')
        .select('*', { count: 'exact', head: true })

      // Get active users
      const { count: activeUsers } = await supabase
        .from('profiles')
        .select('*', { count: 'exact', head: true })
        .eq('is_active', true)

      // Get total tasks
      const { count: totalTasks } = await supabase
        .from('tasks')
        .select('*', { count: 'exact', head: true })
        .eq('is_deleted', false)

      // Get tasks by status
      const { data: statusData } = await supabase
        .from('tasks')
        .select('status')
        .eq('is_deleted', false)

      // Get tasks by priority
      const { data: priorityData } = await supabase
        .from('tasks')
        .select('priority')
        .eq('is_deleted', false)

      // Get recent activities (last 7 days)
      const sevenDaysAgo = new Date()
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7)
      
      const { count: recentActivities } = await supabase
        .from('audit_logs')
        .select('*', { count: 'exact', head: true })
        .gte('timestamp', sevenDaysAgo.toISOString())

      // Process status counts
      const tasksByStatus = (statusData || []).reduce((acc, task) => {
        acc[task.status] = (acc[task.status] || 0) + 1
        return acc
      }, {} as Record<string, number>)

      // Process priority counts
      const tasksByPriority = (priorityData || []).reduce((acc, task) => {
        acc[task.priority] = (acc[task.priority] || 0) + 1
        return acc
      }, {} as Record<string, number>)

      return {
        total_users: totalUsers || 0,
        active_users: activeUsers || 0,
        total_tasks: totalTasks || 0,
        tasks_by_status: tasksByStatus,
        tasks_by_priority: tasksByPriority,
        recent_activities: recentActivities || 0,
      }
    } catch (error: any) {
      console.error('Error getting system stats:', error)
      throw new Error(error.message)
    }
  },

  getAuditLogs: async (params?: {
    page?: number
    size?: number
    user_id?: string
    action?: string
  }): Promise<PaginatedResponse<AuditLog>> => {
    const page = params?.page || 1
    const size = params?.size || 20
    const from = (page - 1) * size
    const to = from + size - 1

    let query = supabase
      .from('audit_logs')
      .select('*', { count: 'exact' })
      .order('timestamp', { ascending: false })

    if (params?.user_id) {
      query = query.eq('user_id', params.user_id)
    }

    if (params?.action) {
      query = query.ilike('action', `%${params.action}%`)
    }

    const { data, error, count } = await query.range(from, to)

    if (error) throw new Error(error.message)

    return {
      data: data || [],
      total: count || 0,
      page,
      size,
    }
  },

  getUsers: async (params?: {
    page?: number
    size?: number
  }): Promise<PaginatedResponse<User>> => {
    const page = params?.page || 1
    const size = params?.size || 10
    const from = (page - 1) * size
    const to = from + size - 1

    const { data, error, count } = await supabase
      .from('profiles')
      .select('*', { count: 'exact' })
      .order('created_at', { ascending: false })
      .range(from, to)

    if (error) throw new Error(error.message)

    // We need to get emails from auth.users, but that's not directly accessible
    // For now, we'll return profiles without emails for admin view
    const users: User[] = (data || []).map(profile => ({
      id: profile.id,
      email: '', // Email not accessible from profiles table
      username: profile.username,
      role: profile.role,
      is_active: profile.is_active,
      created_at: profile.created_at,
      updated_at: profile.updated_at,
    }))

    return {
      data: users,
      total: count || 0,
      page,
      size,
    }
  },

  bulkAssignTasks: async (taskIds: number[], userId: string) => {
    const { data, error } = await supabase
      .from('tasks')
      .update({ assigned_user_id: userId })
      .in('id', taskIds)
      .select()

    if (error) throw new Error(error.message)
    return data
  },
}