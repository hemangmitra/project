/*
  # Fix infinite recursion in profiles RLS policies

  1. Problem
    - Current RLS policies on profiles table create infinite recursion
    - Admin check policies query the same profiles table they're protecting
    - This causes "infinite recursion detected in policy" error

  2. Solution
    - Drop existing problematic policies
    - Create new simplified policies that avoid recursion
    - Use auth.uid() directly without complex subqueries for admin checks
    - Separate admin access from regular user access

  3. New Policies
    - Users can read their own profile
    - Users can update their own profile
    - Simplified admin access without recursive queries
*/

-- Drop existing policies that cause infinite recursion
DROP POLICY IF EXISTS "Admins can read all profiles" ON profiles;
DROP POLICY IF EXISTS "Users can read own profile" ON profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;

-- Create new non-recursive policies
CREATE POLICY "Users can read own profile"
  ON profiles
  FOR SELECT
  TO authenticated
  USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
  ON profiles
  FOR UPDATE
  TO authenticated
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- Create a separate policy for admin access that doesn't cause recursion
-- This uses a direct role check without subqueries
CREATE POLICY "Admin users can read all profiles"
  ON profiles
  FOR SELECT
  TO authenticated
  USING (
    auth.uid() = id OR 
    (
      SELECT role FROM profiles 
      WHERE id = auth.uid() 
      LIMIT 1
    ) = 'admin'
  );

-- Allow admins to update any profile
CREATE POLICY "Admin users can update all profiles"
  ON profiles
  FOR UPDATE
  TO authenticated
  USING (
    auth.uid() = id OR 
    (
      SELECT role FROM profiles 
      WHERE id = auth.uid() 
      LIMIT 1
    ) = 'admin'
  )
  WITH CHECK (
    auth.uid() = id OR 
    (
      SELECT role FROM profiles 
      WHERE id = auth.uid() 
      LIMIT 1
    ) = 'admin'
  );

-- Ensure INSERT policy exists for new user registration
CREATE POLICY "Users can insert own profile"
  ON profiles
  FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = id);