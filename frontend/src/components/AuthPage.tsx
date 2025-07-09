import React, { useState } from 'react';
import { LoginForm } from './LoginForm';
import { RegisterForm } from './RegisterForm';
import { useAuth } from '@/contexts/AuthContext';

export function AuthPage() {
  const [isLoginMode, setIsLoginMode] = useState(true);
  const { login, register, isLoading, error } = useAuth();

  const handleLogin = async (email: string, password: string) => {
    await login(email, password);
  };

  const handleRegister = async (email: string, password: string, firstName: string, lastName: string) => {
    await register(email, password, firstName, lastName);
  };

  const switchToRegister = () => setIsLoginMode(false);
  const switchToLogin = () => setIsLoginMode(true);

  if (isLoginMode) {
    return (
      <LoginForm
        onLogin={handleLogin}
        onSwitchToRegister={switchToRegister}
        isLoading={isLoading}
        error={error}
      />
    );
  }

  return (
    <RegisterForm
      onRegister={handleRegister}
      onSwitchToLogin={switchToLogin}
      isLoading={isLoading}
    />
  );
}