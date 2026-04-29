import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ProductSidePanel from '../../components/ProductSidePanel';
import StudentSettings from './components/StudentSettings';
import { useAuth } from '@/hooks/use-auth';
import { authService } from '@/services/auth';
import { courseService } from '@/services/course';
import { dashboardService } from '@/services/dashboard';
import { notificationService } from '@/services/notifications';
import type {
  DashboardNotification,
  DashboardTone,
  StudentDashboardData,
} from '@/types/dashboard';

const toneClassMap: Record<DashboardTone, string> = {
  blue: 'bg-blue-500',
  green: 'bg-green-500',
  purple: 'bg-purple-500',
  orange: 'bg-orange-500',
  teal: 'bg-teal-500',
  red: 'bg-red-500',
  amber: 'bg-amber-500',
  pink: 'bg-pink-500',
};

const toneSurfaceClassMap: Record<DashboardTone, string> = {
  blue: 'bg-blue-50',
  green: 'bg-green-50',
  purple: 'bg-purple-50',
  orange: 'bg-orange-50',
  teal: 'bg-teal-50',
  red: 'bg-red-50',
  amber: 'bg-amber-50',
  pink: 'bg-pink-50',
};

const toneBorderClassMap: Record<DashboardTone, string> = {
  blue: 'border-blue-100',
  green: 'border-green-100',
  purple: 'border-purple-100',
  orange: 'border-orange-100',
  teal: 'border-teal-100',
  red: 'border-red-100',
  amber: 'border-amber-100',
  pink: 'border-pink-100',
};

const toneTextClassMap: Record<DashboardTone, string> = {
  blue: 'text-blue-600',
  green: 'text-green-600',
  purple: 'text-purple-600',
  orange: 'text-orange-600',
  teal: 'text-teal-600',
  red: 'text-red-600',
  amber: 'text-amber-600',
  pink: 'text-pink-600',
};

export default function StudentDashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('learning');
  const [showJoinCourseModal, setShowJoinCourseModal] = useState(false);
  const [inviteCode, setInviteCode] = useState('');
  const [joinCoursePending, setJoinCoursePending] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [dashboardData, setDashboardData] = useState<StudentDashboardData | null>(null);
  const [dashboardError, setDashboardError] = useState('');
  const [notificationFilter, setNotificationFilter] = useState('all');
  const [notifications, setNotifications] = useState<DashboardNotification[]>([]);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    let mounted = true;

    dashboardService
      .getStudentDashboard()
      .then((data) => {
        if (!mounted) return;
        setDashboardData(data);
        setNotifications(data.notifications);
        setDashboardError('');
      })
      .catch((error) => {
        if (!mounted) return;
        setDashboardError(error instanceof Error ? error.message : 'Dashboard data failed to load');
      });

    return () => {
      mounted = false;
    };
  }, []);

  const handleLogout = () => {
    authService.logout();
    setShowUserMenu(false);
    navigate('/login');
  };




  const handleJoinCourse = async () => {
    if (!inviteCode.trim()) return;

    setJoinCoursePending(true);

    try {
      await courseService.joinCourse({ inviteCode: inviteCode.trim() });
      setShowJoinCourseModal(false);
      setInviteCode('');
      const data = await dashboardService.getStudentDashboard();
      setDashboardData(data);
      setNotifications(data.notifications);
      setDashboardError('');
    } catch (error) {
      setDashboardError(error instanceof Error ? error.message : 'Failed to join course');
    } finally {
      setJoinCoursePending(false);
    }
  };

  // 跳转到课程空间任务中心的指定作业
  const handleGoToHomework = (courseId: number, homeworkId: string) => {
    // 跳转到课程空间，并携带参数指定打开任务中心和作业ID
    navigate(`/student-course/${courseId}?section=tasks&taskId=${homeworkId}&taskType=homework`);
  };

  // 跳转到课程空间任务中心的考试详情
  const handleGoToExam = (courseId: number, examId: string) => {
    // 跳转到课程空间，并携带参数指定打开任务中心和考试ID
    navigate(`/student-course/${courseId}?section=tasks&taskId=${examId}&taskType=exam`);
  };

  // 跳转到课程空间课程资料的指定章节
  const handleGoToMaterial = (courseId: number, chapterId: string) => {
    // 跳转到课程空间，并携带参数指定打开课程资料和章节ID
    navigate(`/student-course/${courseId}?section=materials&chapterId=${chapterId}`);
  };

  // 新增：获取过滤后的通知
  const getFilteredNotifications = () => {
    if (notificationFilter === 'all') return notifications;
    if (notificationFilter === 'task') return notifications.filter(n => n.type === 'deadline' || n.type === 'exam');
    if (notificationFilter === 'teacher') return notifications.filter(n => n.type === 'reply' || n.type === 'material');
    if (notificationFilter === 'ai') return notifications.filter(n => n.type === 'ai');
    return notifications;
  };

  // 新增：标记所有通知为已读
  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, unread: false })));
    void notificationService
      .markAllAsRead('student')
      .catch((error) => setDashboardError(error instanceof Error ? error.message : 'Failed to mark notifications as read'));
  };

  // 新增：标记单个通知为已读
  const markAsRead = (notificationId: string) => {
    setNotifications(prev => prev.map(n => 
      n.id === notificationId ? { ...n, unread: false } : n
    ));
    void notificationService
      .markAsRead('student', notificationId)
      .catch((error) => setDashboardError(error instanceof Error ? error.message : 'Failed to mark notification as read'));
  };


  const studentCourses = dashboardData?.courses ?? [];
  const progressCourses = dashboardData?.progressCourses ?? [];
  const pendingItems = dashboardData?.pendingItems ?? [];
  const recommendations = dashboardData?.recommendations ?? [];
  const activities = dashboardData?.activities ?? [];
  const displayName = dashboardData?.greetingName || user?.displayName || user?.name || '学生';
  const accountLabel = user?.email || user?.account || '';
  const avatarInitial = displayName.trim().charAt(0) || '学';

  return (
    <div className="soft-dash soft-dash-student min-h-screen bg-gray-50" translate="no">
      {/* 固定导航栏 */}
      <nav className="fixed top-0 left-0 right-0 bg-white border-b border-gray-200 z-50">
        <div className="px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2">
                <img src="https://public.readdy.ai/ai/img_res/2625f127-2f4f-41ee-82d8-6c2fa4dee4ac.png" alt="珞樱学堂" className="h-9 w-9" />
                <span className="text-lg font-semibold text-gray-900">珞樱学堂</span>
              </Link>
              <div className="flex items-center gap-1">
                <button onClick={() => setActiveTab('learning')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'learning' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>学习空间</button>
                <button onClick={() => setActiveTab('courses')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'courses' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>我的课程</button>
                <button onClick={() => setActiveTab('notifications')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors relative ${activeTab === 'notifications' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>
                  通知中心
                  {notifications.filter(n => n.unread).length > 0 && (
                    <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                  )}
                </button>
                <button onClick={() => setActiveTab('profile')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'profile' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>个人设置</button>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-gray-900 cursor-pointer">
                <i className="ri-notification-3-line text-lg"></i>
              </button>
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setShowUserMenu(v => !v)}
                  className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors"
                >
                  <div className="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center text-white text-sm font-medium">{avatarInitial}</div>
                  <span className="text-sm text-gray-700 font-medium">{displayName}</span>
                  <i className={`ri-arrow-down-s-line text-gray-400 text-base transition-transform ${showUserMenu ? 'rotate-180' : ''}`}></i>
                </button>
                {showUserMenu && (
                  <div className="absolute right-0 bottom-full mb-1.5 w-44 origin-bottom-right bg-white border border-gray-200 rounded-xl overflow-hidden z-50">
                    <div className="px-4 py-3 border-b border-gray-100">
                      <div className="text-sm font-semibold text-gray-900">{displayName}</div>
                      {accountLabel && <div className="text-xs text-gray-500 mt-0.5">{accountLabel}</div>}
                    </div>
                    <div className="py-1">
                      <button
                        onClick={() => { setActiveTab('profile'); setShowUserMenu(false); }}
                        className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer"
                      >
                        <i className="ri-user-settings-line text-gray-400 text-base"></i>
                        个人设置
                      </button>
                      <div className="my-1 border-t border-gray-100"></div>
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 cursor-pointer"
                      >
                        <i className="ri-logout-box-r-line text-red-500 text-base"></i>
                        退出登录
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* 主内容区 */}
      <div className="pt-16 px-6 py-6">
        {dashboardError && (
          <div className="max-w-7xl mx-auto mb-4 rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600">
            {dashboardError}
          </div>
        )}
        {activeTab === 'learning' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">学习空间</h1>
            
            {/* 智能问答框 */}
            <div className="bg-gradient-to-r from-teal-500 to-blue-500 rounded-xl p-6 mb-6">
              <h2 className="text-lg font-semibold text-white mb-4">AI助教随时为您解答</h2>
              <div className="bg-white rounded-lg p-4">
                <div className="flex items-center gap-3 mb-3">
                  <select className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                    <option>计算机网络</option>
                    <option>数据结构与算法</option>
                    <option>操作系统原理</option>
                    <option>数据库系统</option>
                  </select>
                  <div className="flex-1 relative">
                    <input type="text" placeholder="输入您的问题,支持图片和语音..." className="w-full px-4 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 pr-20" />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-2">
                      <button className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer">
                        <i className="ri-image-line text-base"></i>
                      </button>
                      <button className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer">
                        <i className="ri-mic-line text-base"></i>
                      </button>
                    </div>
                  </div>
                  <button className="px-5 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap">提问</button>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">快捷问题:</span>
                  <button className="px-3 py-1 text-xs text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 cursor-pointer whitespace-nowrap">TCP三次握手</button>
                  <button className="px-3 py-1 text-xs text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 cursor-pointer whitespace-nowrap">红黑树旋转</button>
                  <button className="px-3 py-1 text-xs text-gray-600 bg-gray-100 rounded-full hover:bg-gray-200 cursor-pointer whitespace-nowrap">进程调度算法</button>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-6">
              {/* 待办事项 */}
              <div className="col-span-2 space-y-4">
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">待办事项</h2>
                  <div className="space-y-3">
                    {pendingItems.map((item) => (
                      <div key={item.id} className={`flex items-center gap-3 p-3 rounded-lg border ${toneSurfaceClassMap[item.tone]} ${toneBorderClassMap[item.tone]}`}>
                        <div className={`w-8 h-8 flex items-center justify-center rounded-lg ${toneSurfaceClassMap[item.tone]} flex-shrink-0`}>
                          <i className={`${item.icon} ${toneTextClassMap[item.tone]} text-base`}></i>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900">{item.title}</div>
                          <div className="text-xs text-gray-600 mt-1">{item.description}</div>
                        </div>
                        <button
                          onClick={() => navigate(item.targetUrl)}
                          className={`px-3 py-1.5 text-xs font-medium ${toneTextClassMap[item.tone]} ${toneSurfaceClassMap[item.tone]} rounded-md hover:bg-white/70 cursor-pointer whitespace-nowrap`}
                        >
                          {item.actionLabel}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 课程进度 */}
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">课程进度</h2>
                  <div className="space-y-4">
                    {progressCourses.map((course, index) => (
                      <div key={index} className="p-3 rounded-lg border border-gray-200 hover:border-gray-300 cursor-pointer">
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-sm font-medium text-gray-900">{course.name}</div>
                          {course.unread > 0 && (
                            <span className="px-2 py-0.5 bg-red-500 text-white text-xs font-medium rounded-full">{course.unread}</span>
                          )}
                        </div>
                        <div className="text-xs text-gray-600 mb-2">{course.chapter}</div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                            <div className={`h-full ${toneClassMap[course.color]} rounded-full`} style={{ width: `${course.progress}%` }}></div>
                          </div>
                          <span className="text-xs font-medium text-gray-600">{course.progress}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 右侧栏 */}
              <div className="space-y-4">
                {/* AI建议 */}
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-purple-50">
                      <i className="ri-lightbulb-line text-purple-600 text-base"></i>
                    </div>
                    <h2 className="text-base font-semibold text-gray-900">AI学习建议</h2>
                  </div>
                  <div className="space-y-3">
                    {recommendations.map((item) => (
                      <div key={item.id} className={`p-3 rounded-lg ${toneSurfaceClassMap[item.tone]}`}>
                        <div className="text-sm font-medium text-gray-900 mb-1">{item.title}</div>
                        <div className="text-xs text-gray-600">{item.content}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 学习动态 */}
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">学习动态</h2>
                  <div className="space-y-3">
                    {activities.map((item) => (
                      <div key={item.id} className="flex items-start gap-2">
                        <div className={`w-6 h-6 flex items-center justify-center rounded-full ${toneSurfaceClassMap[item.tone]} flex-shrink-0`}>
                          <i className={`${item.icon || 'ri-information-line'} ${toneTextClassMap[item.tone]} text-xs`}></i>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs text-gray-900">{item.title}</div>
                          <div className="text-xs text-gray-500 mt-1">{item.content}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'courses' && (
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between mb-6">
              <h1 className="text-2xl font-bold text-gray-900">我的课程</h1>
              <button 
                onClick={() => setShowJoinCourseModal(true)}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                <i className="ri-add-line mr-1"></i>加入课程
              </button>
            </div>

            <div className="grid grid-cols-3 gap-5" translate="no">
              {studentCourses.map((course, index) => (
                <div key={index} className="bg-white rounded-lg border border-gray-200 overflow-hidden hover:shadow-lg transition-shadow cursor-pointer">
                  <div className="relative h-36 w-full">
                    <img src={course.image} alt={course.name} className="w-full h-full object-cover object-top" />
                    {course.unread > 0 && (
                      <div className="absolute top-3 right-3 px-2 py-1 bg-red-500 text-white text-xs font-medium rounded-full">
                        {course.unread} 条新消息
                      </div>
                    )}
                  </div>
                  <div className="p-4">
                    <h3 className="text-base font-semibold text-gray-900 mb-1">{course.name}</h3>
                    <div className="text-xs text-gray-600 mb-3">{course.teacher}</div>
                    <div className="flex items-center gap-2 mb-3">
                      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-teal-500 rounded-full" style={{ width: `${course.progress}%` }}></div>
                      </div>
                      <span className="text-xs font-medium text-gray-600">{course.progress}%</span>
                    </div>
                    <Link 
                      to={`/student-course/${course.id}`}
                      className="block w-full px-3 py-2 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 transition-colors cursor-pointer whitespace-nowrap text-center"
                    >
                      进入学习
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'notifications' && (
          <div className="max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">通知中心</h1>
            
            <div className="bg-white rounded-lg border border-gray-200">
              <div className="border-b border-gray-200 px-5 py-3">
                <div className="flex items-center gap-2">
                  <button 
                    onClick={() => setNotificationFilter('all')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${notificationFilter === 'all' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                  >
                    全部
                  </button>
                  <button 
                    onClick={() => setNotificationFilter('task')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${notificationFilter === 'task' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                  >
                    任务提醒
                  </button>
                  <button 
                    onClick={() => setNotificationFilter('teacher')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${notificationFilter === 'teacher' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                  >
                    教师互动
                  </button>
                  <button 
                    onClick={() => setNotificationFilter('ai')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${notificationFilter === 'ai' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                  >
                    AI建议
                  </button>
                  <div className="flex-1"></div>
                  <button 
                    onClick={markAllAsRead}
                    className="text-sm text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap"
                  >
                    全部已读
                  </button>
                </div>
              </div>
              
              <div className="divide-y divide-gray-100" translate="no">
                {getFilteredNotifications().map((notif) => (
                  <div 
                    key={notif.id} 
                    className={`px-5 py-4 hover:bg-gray-50 cursor-pointer ${notif.unread ? 'bg-blue-50/30' : ''}`}
                    onClick={() => markAsRead(notif.id)}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${
                        notif.type === 'deadline' ? 'bg-red-50' :
                        notif.type === 'reply' ? 'bg-blue-50' :
                        notif.type === 'exam' ? 'bg-orange-50' :
                        notif.type === 'ai' ? 'bg-purple-50' :
                        'bg-green-50'
                      }`}>
                        <i className={`text-base ${
                          notif.type === 'deadline' ? 'ri-alarm-warning-line text-red-600' :
                          notif.type === 'reply' ? 'ri-chat-3-line text-blue-600' :
                          notif.type === 'exam' ? 'ri-file-list-3-line text-orange-600' :
                          notif.type === 'ai' ? 'ri-lightbulb-line text-purple-600' :
                          'ri-file-text-line text-green-600'
                        }`}></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="text-sm font-semibold text-gray-900">{notif.title}</h3>
                          {notif.unread && <span className="w-2 h-2 bg-teal-500 rounded-full"></span>}
                        </div>
                        <p className="text-sm text-gray-600">{notif.content}</p>
                        <div className="text-xs text-gray-400 mt-2">{notif.time}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'profile' && (
          <div className="max-w-7xl mx-auto">
            <StudentSettings />
          </div>
        )}
      </div>

      {/* 加入课程弹窗 */}
      {showJoinCourseModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">加入课程</h2>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">课程邀请码</label>
                <input 
                  type="text" 
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                  placeholder="请输入课程邀请码" 
                  maxLength={20}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 uppercase tracking-wider" 
                />
                <p className="text-xs text-gray-500 mt-2">请向教师索取课程邀请码</p>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-500 mb-3">或扫描二维码加入</div>
                <div className="bg-gray-50 rounded-lg p-4 flex items-center justify-center">
                  <div className="w-32 h-32 bg-white rounded-lg flex items-center justify-center">
                    <i className="ri-qr-scan-2-line text-6xl text-gray-300"></i>
                  </div>
                </div>
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3">
              <button 
                onClick={() => {
                  setShowJoinCourseModal(false);
                  setInviteCode('');
                }}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
              >
                取消
              </button>
              <button 
                onClick={handleJoinCourse}
                disabled={!inviteCode.trim() || joinCoursePending}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
              >
                加入课程
              </button>
            </div>
          </div>
        </div>
      )}


      <ProductSidePanel role="student" />
    </div>
  );
}
