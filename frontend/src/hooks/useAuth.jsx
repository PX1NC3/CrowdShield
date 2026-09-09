/**
 * CrowdShield Auth Context
 * Manages active user role ('user' | 'manager') and session state.
 */
import { createContext, useContext, useState, useEffect } from 'react';

const AUTH_ROLE_KEY = 'crowdshield_role';
const DEFAULT_MANAGER_PASS = 'admin123';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // role: 'user' | 'manager' | null (null means modal prompt needed)
  const [role, setRole] = useState(() => {
    return sessionStorage.getItem(AUTH_ROLE_KEY) || null;
  });

  const [showRoleModal, setShowRoleModal] = useState(() => {
    return !sessionStorage.getItem(AUTH_ROLE_KEY);
  });

  const selectUserRole = () => {
    sessionStorage.setItem(AUTH_ROLE_KEY, 'user');
    setRole('user');
    setShowRoleModal(false);
  };

  const selectManagerRole = (password) => {
    if (password === DEFAULT_MANAGER_PASS) {
      sessionStorage.setItem(AUTH_ROLE_KEY, 'manager');
      setRole('manager');
      setShowRoleModal(false);
      return { success: true };
    }
    return { success: false, error: 'Incorrect manager password. (Hint: admin123)' };
  };

  const switchRolePrompt = () => {
    setShowRoleModal(true);
  };

  const logout = () => {
    sessionStorage.removeItem(AUTH_ROLE_KEY);
    setRole(null);
    setShowRoleModal(true);
  };

  return (
    <AuthContext.Provider
      value={{
        role: role || 'user',
        isManager: role === 'manager',
        isUser: role === 'user',
        hasChosenRole: Boolean(role),
        showRoleModal,
        selectUserRole,
        selectManagerRole,
        switchRolePrompt,
        logout,
        defaultManagerPass: DEFAULT_MANAGER_PASS,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
