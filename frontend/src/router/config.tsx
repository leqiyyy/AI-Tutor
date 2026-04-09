import { lazy } from 'react';
import { RouteObject } from 'react-router-dom';

const Home = lazy(() => import('../pages/home/page'));
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
  {
    path: '/teacher-dashboard',
    element: <TeacherDashboard />,
  },
  {
    path: '/student-dashboard',
    element: <StudentDashboard />,
  },
  {
    path: '/admin-dashboard',
    element: <AdminDashboard />,
  },
  {
    path: '/teacher-course/:id',
    element: <TeacherCourse />,
  },
  {
    path: '/student-course/:id',
    element: <StudentCourse />,
  },
  {
    path: '*',
    element: <NotFound />,
  },
];

export default routes;