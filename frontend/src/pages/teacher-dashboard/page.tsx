import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ProductSidePanel from '../../components/ProductSidePanel';
import TeacherSettings from './components/TeacherSettings';
import { authService } from '@/services/auth';
import { courseService } from '@/services/course';
import { dashboardService } from '@/services/dashboard';
import { notificationService } from '@/services/notifications';
import type { DashboardNotification, TeacherDashboardData } from '@/types/dashboard';

export default function TeacherDashboard() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [dashboardData, setDashboardData] = useState<TeacherDashboardData | null>(null);
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
      .getTeacherDashboard()
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
  const [showCreateCourseModal, setShowCreateCourseModal] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [createStep, setCreateStep] = useState(1);
  const [newCourse, setNewCourse] = useState({
    name: '',
    code: '',
    semester: '',
    description: '',
    coverColor: '#3b82f6'
  });
  const [inviteCode, setInviteCode] = useState('');
  const [createCoursePending, setCreateCoursePending] = useState(false);

  // 新增：教学日历相关状态
  const [calendarView, setCalendarView] = useState<'week' | 'month'>('week');
  const [currentMonth, setCurrentMonth] = useState(new Date());


  // 新增：个人设置相关状态
  const [profileForm, setProfileForm] = useState({
    name: '王教授',
    bio: '',
    email: 'wang@university.edu.cn',
    phone: '',
    school: '',
    department: '',
    title: ''
  });
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    oldPassword: '',
    newPassword: '',
    confirmPassword: ''
  });
  const [showDevicesModal, setShowDevicesModal] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState('');

  const handleCreateCourse = async () => {
    setCreateCoursePending(true);

    try {
      const result = await courseService.createCourse(newCourse);
      setInviteCode(result.inviteCode);
      setCreateStep(2);
      const data = await dashboardService.getTeacherDashboard();
      setDashboardData(data);
      setNotifications(data.notifications);
      setDashboardError('');
    } catch (error) {
      setDashboardError(error instanceof Error ? error.message : 'Failed to create course');
    } finally {
      setCreateCoursePending(false);
    }
  };

  const handleCopyInviteCode = () => {
    navigator.clipboard.writeText(inviteCode);
    alert('邀请码已复制到剪贴板');
  };

  const handleFinishCreate = () => {
    setShowCreateCourseModal(false);
    setCreateStep(1);
    setNewCourse({
      name: '',
      code: '',
      semester: '',
      description: '',
      coverColor: '#3b82f6'
    });
    // 这里可以添加课程到列表的逻辑
  };

  // 新增：生成月历数据
  const generateMonthCalendar = () => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDate = new Date(firstDay);
    startDate.setDate(startDate.getDate() - firstDay.getDay());
    
    const calendar: Date[][] = [];
    let week: Date[] = [];
    
    for (let i = 0; i < 42; i++) {
      const date = new Date(startDate);
      date.setDate(date.getDate() + i);
      week.push(date);
      
      if (week.length === 7) {
        calendar.push(week);
        week = [];
      }
    }
    
    return calendar;
  };

  // 新增：获取日期的事件
  const getDateEvents = (date: Date) => {
    const events = [
      { date: 15, title: '计算机网络授课', color: 'blue' },
      { date: 17, title: '作业截止', color: 'orange' },
      { date: 19, title: '在线答疑', color: 'green' },
      { date: 21, title: '期中考试', color: 'purple' }
    ];
    
    return events.filter(e => e.date === date.getDate() && date.getMonth() === currentMonth.getMonth());
  };

  // 新增：标记所有通知为已读
  const markAllAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, unread: false })));
    void notificationService
      .markAllAsRead('teacher')
      .catch((error) => setDashboardError(error instanceof Error ? error.message : 'Failed to mark notifications as read'));
  };

  // 新增：获取过滤后的通知
  const getFilteredNotifications = () => {
    if (notificationFilter === 'all') return notifications;
    if (notificationFilter === 'student') return notifications.filter(n => n.type === 'question');
    if (notificationFilter === 'ai') return notifications.filter(n => n.type === 'dislike');
    if (notificationFilter === 'task') return notifications.filter(n => n.type === 'deadline');
    return notifications;
  };

  // 新增：保存个人资料
  const handleSaveProfile = () => {
    // 这里应该调用后端API保存数据
    console.log('保存个人资料:', profileForm);
    alert('个人资料已保存');
  };

  // 新增：修改密码
  const handleChangePassword = () => {
    if (!passwordForm.oldPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
      alert('请填写完整的密码信息');
      return;
    }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      alert('两次输入的新密码不一致');
      return;
    }
    if (passwordForm.newPassword.length < 6) {
      alert('新密码长度不能少于6位');
      return;
    }
    // 这里应该调用后端API修改密码
    console.log('修改密码');
    alert('密码修改成功');
    setShowPasswordModal(false);
    setPasswordForm({ oldPassword: '', newPassword: '', confirmPassword: '' });
  };

  // 新增：处理头像上传
  const handleAvatarUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const teacherCourses = dashboardData?.courses ?? [];
  const teacherStats = dashboardData?.stats;
  const weeklyStudentTrend = teacherStats?.weeklyStudentTrend ?? [60, 72, 65, 80, 70, 88, 75];
  const calendarEvents = dashboardData?.calendarEvents ?? [];
  const aiWeeklyMetrics = (dashboardData?.aiWeeklyMetrics ?? []).map((item) => ({
    label: item.title,
    value: item.content,
    change: item.meta || '',
    icon: item.icon || 'ri-line-chart-line',
    color: item.tone,
    good: item.id.includes('dislike'),
  }));
  const hotQuestionTopics = dashboardData?.hotQuestionTopics ?? [];
  const teacherTodoItems = (dashboardData?.todoItems ?? []).map((item) => ({
    title: item.title,
    desc: item.content,
    urgency: item.tone === 'red' ? 'high' : 'mid',
    icon: item.icon || 'ri-checkbox-circle-line',
    action: item.meta || '',
  }));

  return (
    <div className="soft-dash soft-dash-teacher min-h-screen bg-gray-50">
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
                <button onClick={() => setActiveTab('overview')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'overview' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>工作台</button>
                <button onClick={() => setActiveTab('courses')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'courses' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>我的课程</button>
                <button onClick={() => setActiveTab('notifications')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors relative ${activeTab === 'notifications' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>
                  通知中心
                  {notifications.filter(n => n.unread).length > 0 && (
                    <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                  )}
                </button>
                <button onClick={() => setActiveTab('settings')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'settings' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>个人设置</button>
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
                  <div className="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center text-white text-sm font-medium">王</div>
                  <span className="text-sm text-gray-700 font-medium">王教授</span>
                  <i className={`ri-arrow-down-s-line text-gray-400 text-base transition-transform ${showUserMenu ? 'rotate-180' : ''}`}></i>
                </button>
                {showUserMenu && (
                  <div className="absolute right-0 bottom-full mb-1.5 w-44 origin-bottom-right bg-white border border-gray-200 rounded-xl overflow-hidden z-50">
                    <div className="px-4 py-3 border-b border-gray-100">
                      <div className="text-sm font-semibold text-gray-900">王教授</div>
                      <div className="text-xs text-gray-500 mt-0.5">wang@university.edu.cn</div>
                    </div>
                    <div className="py-1">
                      <button
                        onClick={() => { setActiveTab('settings'); setShowUserMenu(false); }}
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
        {activeTab === 'overview' && (
          <div className="max-w-7xl mx-auto">
            {/* 欢迎横幅 */}
            <div className="bg-gradient-to-r from-teal-600 to-teal-500 rounded-xl p-6 mb-6 relative overflow-hidden">
              <div className="absolute inset-0 opacity-10">
                <div className="absolute -right-12 -top-12 w-48 h-48 rounded-full bg-white"></div>
                <div className="absolute -right-4 -bottom-16 w-64 h-64 rounded-full bg-white"></div>
              </div>
              <div className="relative flex items-center justify-between">
                <div>
                  <div className="text-white/80 text-sm mb-1">早上好，王教授 👋</div>
                  <h1 className="text-2xl font-bold text-white mb-2">今日工作台</h1>
                  <div className="flex items-center gap-4 text-white/80 text-sm">
                    <span className="flex items-center gap-1"><i className="ri-calendar-line"></i>2026年4月10日 周五</span>
                    <span className="flex items-center gap-1"><i className="ri-time-line"></i>本学期第12周</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="bg-white/15 rounded-xl px-5 py-4 text-center backdrop-blur-sm border border-white/20">
                    <div className="text-2xl font-bold text-white">{teacherStats?.todayTodo ?? 3}</div>
                    <div className="text-xs text-white/80 mt-0.5">今日待处理</div>
                  </div>
                  <div className="bg-white/15 rounded-xl px-5 py-4 text-center backdrop-blur-sm border border-white/20">
                    <div className="text-2xl font-bold text-white">{teacherStats?.pendingQuestions ?? 15}</div>
                    <div className="text-xs text-white/80 mt-0.5">待审核疑问</div>
                  </div>
                  <div className="bg-white/15 rounded-xl px-5 py-4 text-center backdrop-blur-sm border border-white/20">
                    <div className="text-2xl font-bold text-white">{teacherStats?.dueSoon ?? 2}</div>
                    <div className="text-xs text-white/80 mt-0.5">即将截止</div>
                  </div>
                </div>
              </div>
            </div>

            {/* 数据概览卡片 */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-xl p-5 border border-gray-200 hover:border-teal-200 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">活跃课程</div>
                    <div className="text-3xl font-bold text-gray-900">{teacherStats?.activeCourses ?? 8}</div>
                  </div>
                  <div className="w-10 h-10 flex items-center justify-center rounded-xl bg-teal-50">
                    <i className="ri-book-open-line text-teal-600 text-lg"></i>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">本学期开设</span>
                  <span className="text-xs font-medium text-teal-600 bg-teal-50 px-2 py-0.5 rounded-full">进行中</span>
                </div>
                {/* 迷你进度条 */}
                <div className="mt-3 flex gap-1">
                  {[1,1,1,1,1,1,1,1,0,0].map((v, i) => (
                    <div key={i} className={`flex-1 h-1 rounded-full ${v ? 'bg-teal-500' : 'bg-gray-100'}`}></div>
                  ))}
                </div>
                <div className="text-xs text-gray-400 mt-1">8/10 课程配置完成</div>
              </div>

              <div className="bg-white rounded-xl p-5 border border-gray-200 hover:border-green-200 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">学生总数</div>
                    <div className="text-3xl font-bold text-gray-900">{teacherStats?.totalStudents ?? 342}</div>
                  </div>
                  <div className="w-10 h-10 flex items-center justify-center rounded-xl bg-green-50">
                    <i className="ri-group-line text-green-600 text-lg"></i>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">跨6门课程</span>
                  <span className="text-xs font-medium text-green-600">↑ +23 本周</span>
                </div>
                {/* 迷你柱状图 */}
                <div className="mt-3 flex items-end gap-1 h-8">
                  {weeklyStudentTrend.map((h, i) => (
                    <div key={i} className="flex-1 bg-green-100 rounded-sm" style={{ height: `${h}%` }}>
                      <div className="w-full bg-green-400 rounded-sm" style={{ height: i === 6 ? '100%' : '70%' }}></div>
                    </div>
                  ))}
                </div>
                <div className="text-xs text-gray-400 mt-1">近7周活跃学生趋势</div>
              </div>

              <div className="bg-white rounded-xl p-5 border border-gray-200 hover:border-orange-200 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">AI答疑分担率</div>
                    <div className="text-3xl font-bold text-gray-900">{teacherStats?.aiAnswerRate ?? 78}<span className="text-lg text-gray-500">%</span></div>
                  </div>
                  <div className="w-10 h-10 flex items-center justify-center rounded-xl bg-orange-50">
                    <i className="ri-robot-line text-orange-500 text-lg"></i>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-500">本周均值</span>
                  <span className="text-xs font-medium text-orange-500">↑ +5% vs 上周</span>
                </div>
                {/* 环形进度简化版 */}
                <div className="mt-3 w-full bg-gray-100 rounded-full h-1.5">
                  <div className="bg-gradient-to-r from-orange-400 to-orange-500 h-1.5 rounded-full" style={{ width: `${teacherStats?.aiAnswerRate ?? 78}%` }}></div>
                </div>
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>AI自动回复</span>
                  <span>人工处理 22%</span>
                </div>
              </div>

              <div className="bg-white rounded-xl p-5 border border-gray-200 hover:border-amber-200 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">平均满意度</div>
                    <div className="text-3xl font-bold text-gray-900">{teacherStats?.satisfactionScore ?? 4.6}<span className="text-sm text-gray-400 ml-0.5">/5</span></div>
                  </div>
                  <div className="w-10 h-10 flex items-center justify-center rounded-xl bg-amber-50">
                    <i className="ri-star-fill text-amber-500 text-lg"></i>
                  </div>
                </div>
                <div className="flex items-center gap-0.5 mb-3">
                  {[1,2,3,4].map(i => <i key={i} className="ri-star-fill text-amber-400 text-sm"></i>)}
                  <i className="ri-star-half-fill text-amber-400 text-sm"></i>
                </div>
                <div className="flex items-center gap-1 text-xs">
                  <span className="text-amber-500 font-medium">72%</span><span className="text-gray-400">满意</span>
                  <span className="text-gray-200 mx-1">·</span>
                  <span className="text-gray-400 font-medium">20%</span><span className="text-gray-400">一般</span>
                  <span className="text-gray-200 mx-1">·</span>
                  <span className="text-red-400 font-medium">8%</span><span className="text-gray-400">不满意</span>
                </div>
                <div className="mt-2 w-full h-1.5 rounded-full overflow-hidden flex gap-px">
                  <div className="bg-amber-400 rounded-l-full" style={{ width: '72%' }}></div>
                  <div className="bg-gray-200" style={{ width: '20%' }}></div>
                  <div className="bg-red-300 rounded-r-full" style={{ width: '8%' }}></div>
                </div>
              </div>
            </div>

            {/* 主体三列布局 */}
            <div className="grid grid-cols-12 gap-5">
              {/* 左侧：日程 + AI表现 */}
              <div className="col-span-8 space-y-5">
                {/* 本周日程 */}
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-base font-semibold text-gray-900">本周教学日程</h2>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setCalendarView('week')}
                        className={`px-3 py-1 text-xs font-medium rounded-full transition-colors cursor-pointer whitespace-nowrap ${calendarView === 'week' ? 'bg-teal-100 text-teal-700' : 'text-gray-500 hover:text-gray-700'}`}
                      >周视图</button>
                      <button
                        onClick={() => setCalendarView('month')}
                        className={`px-3 py-1 text-xs font-medium rounded-full transition-colors cursor-pointer whitespace-nowrap ${calendarView === 'month' ? 'bg-teal-100 text-teal-700' : 'text-gray-500 hover:text-gray-700'}`}
                      >月视图</button>
                    </div>
                  </div>

                  {calendarView === 'week' ? (
                    <div className="grid grid-cols-2 gap-3">
                      {calendarEvents.map((item, idx) => (
                        <div key={idx} className={`flex items-start gap-3 p-4 rounded-xl border transition-colors cursor-pointer hover:border-gray-300 ${
                          item.tagColor === 'teal' ? 'bg-teal-50/50 border-teal-100' :
                          item.tagColor === 'orange' ? 'bg-orange-50/50 border-orange-100' :
                          item.tagColor === 'green' ? 'bg-green-50/50 border-green-100' :
                          'bg-red-50/50 border-red-100'
                        }`}>
                          <div className={`w-10 h-10 flex items-center justify-center rounded-xl flex-shrink-0 ${
                            item.tagColor === 'teal' ? 'bg-teal-100' :
                            item.tagColor === 'orange' ? 'bg-orange-100' :
                            item.tagColor === 'green' ? 'bg-green-100' : 'bg-red-100'
                          }`}>
                            <i className={`${item.icon} text-base ${
                              item.tagColor === 'teal' ? 'text-teal-600' :
                              item.tagColor === 'orange' ? 'text-orange-600' :
                              item.tagColor === 'green' ? 'text-green-600' : 'text-red-600'
                            }`}></i>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                                item.tagColor === 'teal' ? 'bg-teal-100 text-teal-700' :
                                item.tagColor === 'orange' ? 'bg-orange-100 text-orange-700' :
                                item.tagColor === 'green' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                              }`}>{item.tag}</span>
                              <span className="text-xs text-gray-500">{item.day} · {item.date}日</span>
                            </div>
                            <div className="text-sm font-medium text-gray-900 leading-snug">{item.title}</div>
                            <div className="text-xs text-gray-500 mt-0.5">{item.sub}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div>
                      <div className="flex items-center justify-between mb-4">
                        <button onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1))} className="w-7 h-7 flex items-center justify-center text-gray-500 hover:bg-gray-100 rounded cursor-pointer"><i className="ri-arrow-left-s-line"></i></button>
                        <div className="text-sm font-semibold text-gray-900">{currentMonth.getFullYear()}年{currentMonth.getMonth() + 1}月</div>
                        <button onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1))} className="w-7 h-7 flex items-center justify-center text-gray-500 hover:bg-gray-100 rounded cursor-pointer"><i className="ri-arrow-right-s-line"></i></button>
                      </div>
                      <div className="grid grid-cols-7 gap-1 mb-1">
                        {['日','一','二','三','四','五','六'].map((d, i) => (
                          <div key={i} className="text-center text-xs text-gray-400 py-1">{d}</div>
                        ))}
                      </div>
                      <div className="grid grid-cols-7 gap-1">
                        {generateMonthCalendar().map((week, wi) =>
                          week.map((date, di) => {
                            const isCurMonth = date.getMonth() === currentMonth.getMonth();
                            const isToday = date.toDateString() === new Date().toDateString();
                            const evts = getDateEvents(date);
                            return (
                              <div key={`${wi}-${di}`} className={`min-h-[52px] p-1 rounded-lg border transition-colors cursor-pointer ${isCurMonth ? 'hover:bg-gray-50 border-gray-100' : 'border-transparent'} ${isToday ? 'ring-1 ring-teal-400 bg-teal-50/30' : ''}`}>
                                <div className={`text-xs font-medium mb-0.5 ${isCurMonth ? 'text-gray-800' : 'text-gray-300'} ${isToday ? 'text-teal-600' : ''}`}>{date.getDate()}</div>
                                {evts.map((ev, ei) => (
                                  <div key={ei} className={`text-xs px-1 py-0.5 rounded truncate leading-tight mb-0.5 ${ev.color === 'blue' ? 'bg-teal-100 text-teal-700' : ev.color === 'orange' ? 'bg-orange-100 text-orange-700' : ev.color === 'green' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{ev.title}</div>
                                ))}
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* AI助教本周表现 */}
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-base font-semibold text-gray-900">AI助教本周表现</h2>
                    <button
                      onClick={() => setActiveTab('courses')}
                      className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap"
                    >查看各课程详情 →</button>
                  </div>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    {aiWeeklyMetrics.map((item, idx) => (
                      <div key={idx} className="p-4 rounded-xl bg-gray-50 border border-gray-100">
                        <div className="flex items-center gap-2 mb-2">
                          <div className={`w-7 h-7 flex items-center justify-center rounded-lg ${item.color === 'teal' ? 'bg-teal-100' : item.color === 'red' ? 'bg-red-100' : 'bg-green-100'}`}>
                            <i className={`${item.icon} text-sm ${item.color === 'teal' ? 'text-teal-600' : item.color === 'red' ? 'text-red-500' : 'text-green-600'}`}></i>
                          </div>
                          <span className="text-xs text-gray-500">{item.label}</span>
                        </div>
                        <div className="text-xl font-bold text-gray-900">{item.value}</div>
                        <div className={`text-xs mt-1 font-medium ${
                          item.good ? 'text-green-600' :
                          item.change.startsWith('+') ? 'text-teal-600' : 'text-gray-400'
                        }`}>{item.change} 较上周</div>
                      </div>
                    ))}
                  </div>
                  {/* 高频疑问热点：精简为标签行 */}
                  <div className="border-t border-gray-100 pt-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-gray-400 whitespace-nowrap">高频疑问：</span>
                      {hotQuestionTopics.map((item, idx) => (
                        <span key={idx} className="inline-flex items-center gap-1 px-2.5 py-1 bg-teal-50 text-teal-700 text-xs rounded-full cursor-pointer hover:bg-teal-100 transition-colors whitespace-nowrap">
                          {item.topic}
                          <span className="text-teal-400 font-medium">{item.count}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* 右侧：待处理 + 预警 + 快速入口 */}
              <div className="col-span-4 space-y-5">
                {/* 待处理事项 */}
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-semibold text-gray-900">待处理事项</h2>
                    <span className="text-xs bg-red-100 text-red-600 font-semibold px-2 py-0.5 rounded-full">3 项</span>
                  </div>
                  <div className="space-y-2">
                    {teacherTodoItems.map((item, idx) => (
                      <div key={idx} className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer hover:border-gray-300 transition-colors ${item.urgency === 'high' ? 'border-red-100 bg-red-50/40' : 'border-gray-100'}`}>
                        <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${item.urgency === 'high' ? 'bg-red-100' : 'bg-orange-100'}`}>
                          <i className={`${item.icon} text-sm ${item.urgency === 'high' ? 'text-red-600' : 'text-orange-600'}`}></i>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-semibold text-gray-900">{item.title}</div>
                          <div className="text-xs text-gray-500 mt-0.5 truncate">{item.desc}</div>
                        </div>
                        <span className="text-xs text-teal-600 whitespace-nowrap font-medium">{item.action}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 学生预警 */}
                <div className="bg-white rounded-xl border border-gray-200 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-sm font-semibold text-gray-900">学生学习预警</h2>
                    <span className="text-xs text-orange-600 bg-orange-50 font-medium px-2 py-0.5 rounded-full">2 条</span>
                  </div>
                  <div className="space-y-3">
                    <div className="p-3 rounded-lg bg-orange-50/60 border border-orange-100">
                      <div className="flex items-start gap-2">
                        <i className="ri-alert-line text-orange-500 text-sm mt-0.5"></i>
                        <div>
                          <div className="text-xs font-semibold text-gray-900">连续缺勤预警</div>
                          <div className="text-xs text-gray-600 mt-0.5">计算机网络：12名学生连续3周未登录，建议主动联系</div>
                        </div>
                      </div>
                    </div>
                    <div className="p-3 rounded-lg bg-amber-50/60 border border-amber-100">
                      <div className="flex items-start gap-2">
                        <i className="ri-line-chart-line text-amber-500 text-sm mt-0.5"></i>
                        <div>
                          <div className="text-xs font-semibold text-gray-900">成绩下滑预警</div>
                          <div className="text-xs text-gray-600 mt-0.5">数据结构：6名学生近两次作业得分骤降 &gt;30%</div>
                        </div>
                      </div>
                    </div>
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
                onClick={() => setShowCreateCourseModal(true)}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                <i className="ri-add-line mr-1"></i>创建新课程
              </button>
            </div>

            <div className="grid grid-cols-3 gap-5">
              {teacherCourses.map((course, index) => (
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
                    <h3 className="text-base font-semibold text-gray-900 mb-2">{course.name}</h3>
                    <div className="flex items-center justify-between text-xs text-gray-600">
                      <span className="flex items-center gap-1">
                        <i className="ri-user-line"></i>
                        {course.students} 名学生
                      </span>
                      <span className="font-mono text-gray-500">{course.code}</span>
                    </div>
                    <div className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2">
                      <Link 
                        to={`/teacher-course/${course.id}`}
                        className="flex-1 px-3 py-1.5 text-xs font-medium text-teal-600 bg-teal-50 rounded-md hover:bg-teal-100 transition-colors cursor-pointer whitespace-nowrap text-center"
                      >
                        进入课程
                      </Link>
                      <button 
                        onClick={() => {
                          setInviteCode(Math.random().toString(36).substring(2, 8).toUpperCase());
                          setShowInviteModal(true);
                        }}
                        className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 rounded-md hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap"
                      >
                        <i className="ri-share-line"></i>
                      </button>
                    </div>
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
                    onClick={() => setNotificationFilter('student')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${notificationFilter === 'student' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                  >
                    学生互动
                  </button>
                  <button 
                    onClick={() => setNotificationFilter('ai')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${notificationFilter === 'ai' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                  >
                    AI预警
                  </button>
                  <button 
                    onClick={() => setNotificationFilter('task')}
                    className={`px-3 py-1.5 text-sm font-medium rounded-md cursor-pointer whitespace-nowrap ${notificationFilter === 'task' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                  >
                    任务提醒
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
              
              <div className="divide-y divide-gray-100">
                {getFilteredNotifications().map((notif) => (
                  <div 
                    key={notif.id} 
                    className={`px-5 py-4 hover:bg-gray-50 cursor-pointer ${notif.unread ? 'bg-blue-50/30' : ''}`}
                    onClick={() => {
                      setNotifications(prev => prev.map(n => 
                        n.id === notif.id ? { ...n, unread: false } : n
                      ));
                      void notificationService
                        .markAsRead('teacher', notif.id)
                        .catch((error) => setDashboardError(error instanceof Error ? error.message : 'Failed to mark notification as read'));
                    }}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${
                        notif.type === 'question' ? 'bg-blue-50' :
                        notif.type === 'dislike' ? 'bg-red-50' :
                        notif.type === 'deadline' ? 'bg-orange-50' :
                        'bg-green-50'
                      }`}>
                        <i className={`text-base ${
                          notif.type === 'question' ? 'ri-question-line text-blue-600' :
                          notif.type === 'dislike' ? 'ri-thumb-down-line text-red-600' :
                          notif.type === 'deadline' ? 'ri-time-line text-orange-600' :
                          'ri-checkbox-circle-line text-green-600'
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

        {activeTab === 'settings' && (
          <div className="px-0">
            <TeacherSettings />
          </div>
        )}
      </div>

      {/* 创建课程弹窗 */}
      {showCreateCourseModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-lg">
            {createStep === 1 ? (
              <>
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">创建新课程</h2>
                </div>
                <div className="px-6 py-5 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">课程名称 *</label>
                    <input 
                      type="text" 
                      value={newCourse.name}
                      onChange={(e) => setNewCourse({...newCourse, name: e.target.value})}
                      placeholder="例如:计算机网络" 
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" 
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">课程代码 *</label>
                    <input 
                      type="text" 
                      value={newCourse.code}
                      onChange={(e) => setNewCourse({...newCourse, code: e.target.value})}
                      placeholder="例如:CS301" 
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" 
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">学期 *</label>
                    <select 
                      value={newCourse.semester}
                      onChange={(e) => setNewCourse({...newCourse, semester: e.target.value})}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    >
                      <option value="">请选择学期</option>
                      <option value="2024-2025-1">2024-2025学年第一学期</option>
                      <option value="2024-2025-2">2024-2025学年第二学期</option>
                      <option value="2025-2026-1">2025-2026学年第一学期</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">课程简介</label>
                    <textarea 
                      rows={3}
                      value={newCourse.description}
                      onChange={(e) => setNewCourse({...newCourse, description: e.target.value})}
                      placeholder="简要介绍课程内容和目标..." 
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                    ></textarea>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">封面颜色</label>
                    <div className="flex items-center gap-2">
                      {['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#14b8a6', '#ec4899'].map((color) => (
                        <button
                          key={color}
                          onClick={() => setNewCourse({...newCourse, coverColor: color})}
                          className={`w-10 h-10 rounded-lg cursor-pointer transition-all ${newCourse.coverColor === color ? 'ring-2 ring-offset-2 ring-gray-400' : ''}`}
                          style={{ backgroundColor: color }}
                        ></button>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3">
                  <button 
                    onClick={() => {
                      setShowCreateCourseModal(false);
                      setCreateStep(1);
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                  >
                    取消
                  </button>
                  <button 
                    onClick={handleCreateCourse}
                    disabled={!newCourse.name || !newCourse.code || !newCourse.semester || createCoursePending}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    创建课程
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">课程创建成功</h2>
                </div>
                <div className="px-6 py-5">
                  <div className="text-center mb-6">
                    <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-3">
                      <i className="ri-checkbox-circle-line text-green-600 text-3xl"></i>
                    </div>
                    <p className="text-sm text-gray-600">课程已创建,邀请学生加入吧!</p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4 mb-4">
                    <div className="text-xs text-gray-500 mb-2">课程邀请码</div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 text-2xl font-bold text-gray-900 tracking-wider">{inviteCode}</div>
                      <button 
                        onClick={handleCopyInviteCode}
                        className="px-4 py-2 text-sm font-medium text-teal-600 bg-white border border-teal-600 rounded-lg hover:bg-teal-50 transition-colors cursor-pointer whitespace-nowrap"
                      >
                        <i className="ri-file-copy-line mr-1"></i>复制
                      </button>
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-4 flex items-center justify-center">
                    <div className="w-32 h-32 bg-white rounded-lg flex items-center justify-center">
                      <i className="ri-qr-code-line text-6xl text-gray-300"></i>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 text-center mt-3">学生可扫描二维码或输入邀请码加入课程</p>
                </div>
                <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end">
                  <button 
                    onClick={handleFinishCreate}
                    className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    完成
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* 邀请学生弹窗 */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">邀请学生</h2>
            </div>
            <div className="px-6 py-5">
              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                <div className="text-xs text-gray-500 mb-2">课程邀请码</div>
                <div className="flex items-center gap-3">
                  <div className="flex-1 text-2xl font-bold text-gray-900 tracking-wider">{inviteCode}</div>
                  <button 
                    onClick={handleCopyInviteCode}
                    className="px-4 py-2 text-sm font-medium text-teal-600 bg-white border border-teal-600 rounded-lg hover:bg-teal-50 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    <i className="ri-file-copy-line mr-1"></i>复制
                  </button>
                </div>
              </div>
              <div className="bg-gray-50 rounded-lg p-4 flex items-center justify-center">
                <div className="w-32 h-32 bg-white rounded-lg flex items-center justify-center">
                  <i className="ri-qr-code-line text-6xl text-gray-300"></i>
                </div>
              </div>
              <p className="text-xs text-gray-500 text-center mt-3">学生可扫描二维码或输入邀请码加入课程</p>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end">
              <button 
                onClick={() => setShowInviteModal(false)}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 修改密码弹窗 */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">修改密码</h2>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">当前密码</label>
                <input
                  type="password"
                  value={passwordForm.oldPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, oldPassword: e.target.value })}
                  placeholder="请输入当前密码"
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">新密码</label>
                <input
                  type="password"
                  value={passwordForm.newPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                  placeholder="请输入新密码（至少6位）"
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">确认新密码</label>
                <input
                  type="password"
                  value={passwordForm.confirmPassword}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                  placeholder="请再次输入新密码"
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3">
              <button
                onClick={() => {
                  setShowPasswordModal(false);
                  setPasswordForm({ oldPassword: '', newPassword: '', confirmPassword: '' });
                }}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
              >
                取消
              </button>
              <button
                onClick={handleChangePassword}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                确认修改
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 登录设备管理弹窗 */}
      {showDevicesModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
              <h2 className="text-lg font-semibold text-gray-900">登录设备管理</h2>
            </div>
            <div className="px-6 py-5 overflow-y-auto flex-1">
              <div className="space-y-3">
                {[
                  { device: 'Windows PC', browser: 'Chrome 120', location: '武汉市', ip: '192.168.1.100', time: '当前设备', current: true },
                  { device: 'iPhone 13', browser: 'Safari', location: '武汉市', ip: '192.168.1.101', time: '2小时前', current: false },
                  { device: 'MacBook Pro', browser: 'Chrome 119', location: '北京市', ip: '10.0.0.50', time: '1天前', current: false }
                ].map((device, index) => (
                  <div key={index} className="flex items-start gap-4 p-4 border border-gray-200 rounded-lg hover:border-teal-200 transition-colors">
                    <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 flex-shrink-0">
                      <i className={`text-lg ${
                        device.device.includes('Windows') ? 'ri-windows-line text-blue-600' :
                        device.device.includes('iPhone') ? 'ri-smartphone-line text-gray-700' :
                        'ri-macbook-line text-gray-700'
                      }`}></i>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-gray-900">{device.device}</span>
                        {device.current && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-teal-50 text-teal-600 rounded-full">当前设备</span>
                        )}
                      </div>
                      <div className="text-xs text-gray-600 space-y-0.5">
                        <div>{device.browser} · {device.location}</div>
                        <div>IP: {device.ip} · {device.time}</div>
                      </div>
                    </div>
                    {!device.current && (
                      <button className="px-3 py-1.5 text-xs font-medium text-red-600 hover:text-red-700 cursor-pointer whitespace-nowrap">
                        移除
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end flex-shrink-0">
              <button
                onClick={() => setShowDevicesModal(false)}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
      <ProductSidePanel role="teacher" />
    </div>
  );
}
