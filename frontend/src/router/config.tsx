import { lazy } from 'react';
import { RouteObject } from 'react-router-dom';
import { PublicOnlyRoute, RequireAuth } from './guards';

const Login = lazy(() => import('../pages/login/page'));
const Register = lazy(() => import('../pages/register/page'));
const TeacherDashboard = lazy(() => import('../pages/teacher-dashboard/page'));
const StudentDashboard = lazy(() => import('../pages/student-dashboard/page'));
const AdminDashboard = lazy(() => import('../pages/admin-dashboard/page'));
const TeacherCourse = lazy(() => import('../pages/teacher-course/page'));
const StudentCourse = lazy(() => import('../pages/student-course/page'));
const NotFound = lazy(() => import('../pages/NotFound'));

const routes: RouteObject[] = [
  {
    element: <PublicOnlyRoute />,
    children: [
      {
        path: '/',
        element: <Login />,
      },
      {
        path: '/login',
        element: <Login />,
      },
      {
        path: '/register',
        element: <Register />,
      },
    ],
  },
  {
    element: <RequireAuth allowedRoles={['teacher']} />,
    children: [
      {
        path: '/teacher-dashboard',
        element: <TeacherDashboard />,
      },
      {
        path: '/teacher-course/:id',
        element: <TeacherCourse />,
      },
    ],
  },
  {
    element: <RequireAuth allowedRoles={['student']} />,
    children: [
      {
        path: '/student-dashboard',
        element: <StudentDashboard />,
      },
      {
        path: '/student-course/:id',
        element: <StudentCourse />,
      },
    ],
  },
  {
    element: <RequireAuth allowedRoles={['admin']} />,
    children: [
      {
        path: '/admin-dashboard',
        element: <AdminDashboard />,
      },
    ],
  },
  {
    path: '*',
    element: <NotFound />,
  },
];

export default routes;
