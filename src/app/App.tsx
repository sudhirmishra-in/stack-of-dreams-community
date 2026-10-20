import { BrowserRouter } from 'react-router';
import { AppRoutes } from './router';
import { AuthProvider } from '../auth/AuthContext';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
