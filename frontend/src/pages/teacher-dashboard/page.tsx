import { useState } from 'react';
import { Link } from 'react-router-dom';

export default function TeacherDashboard() {
  const [activeTab, setActiveTab] = useState('overview');
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

  // 新增：教学日历相关状态
  const [calendarView, setCalendarView] = useState<'week' | 'month'>('week');
  const [currentMonth, setCurrentMonth] = useState(new Date());

  // 新增：通知中心相关状态
  const [notificationFilter, setNotificationFilter] = useState('all');
  const [notifications, setNotifications] = useState([
    { id: 1, type: 'question', title: '学生提问待审核', content: '张三在"计算机网络"课程中提问:TCP三次握手的第三次握手可以携带数据吗?', time: '10分钟前', unread: true },
    { id: 2, type: 'dislike', title: 'AI回答被点踩', content: '"数据结构"课程中关于"红黑树旋转"的AI回答被3名学生点踩', time: '1小时前', unread: true },
    { id: 3, type: 'deadline', title: '作业截止提醒', content: '"操作系统"课程作业将在3小时后截止,当前还有12名学生未提交', time: '2小时前', unread: false },
    { id: 4, type: 'system', title: '知识库更新完成', content: '"数据库系统"课程新上传的3份资料已完成知识图谱构建', time: '5小时前', unread: false },
    { id: 5, type: 'question', title: '高频疑问提示', content: '"计算机网络"课程中"子网划分"相关问题本周被问询23次,建议集中答疑', time: '1天前', unread: false }
  ]);

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

  const handleCreateCourse = () => {
    // 生成6位随机邀请码
    const code = Math.random().toString(36).substring(2, 8).toUpperCase();
    setInviteCode(code);
    setCreateStep(2);
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

  return (
    <div className="min-h-screen bg-gray-50">
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
              <div className="w-8 h-8 rounded-full bg-teal-500 flex items-center justify-center text-white text-sm font-medium cursor-pointer">王</div>
            </div>
          </div>
        </div>
      </nav>

      {/* 主内容区 */}
      <div className="pt-16 px-6 py-6">
        {activeTab === 'overview' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">工作台</h1>
            
            {/* 数据概览 */}
            <div className="grid grid-cols-5 gap-4 mb-6">
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">活跃课程</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-blue-50">
                    <i className="ri-book-open-line text-blue-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">8</div>
                <div className="text-xs text-gray-500 mt-1">本学期</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">学生总数</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-green-50">
                    <i className="ri-group-line text-green-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">342</div>
                <div className="text-xs text-green-600 mt-1">+23 本周</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">待审核疑问</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-orange-50 relative">
                    <i className="ri-question-line text-orange-600 text-base"></i>
                    <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full"></span>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">15</div>
                <div className="text-xs text-orange-600 mt-1">需处理</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">AI答疑分担率</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-purple-50">
                    <i className="ri-robot-line text-purple-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">78%</div>
                <div className="text-xs text-gray-500 mt-1">较上周 +5%</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">平均满意度</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-teal-50">
                    <i className="ri-star-line text-teal-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">4.6</div>
                <div className="text-xs text-gray-500 mt-1">满分 5.0</div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-6">
              {/* 教学日历 */}
              <div className="col-span-2 bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-gray-900">教学日历</h2>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => setCalendarView('month')}
                      className={`px-3 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer whitespace-nowrap ${calendarView === 'month' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                    >
                      月视图
                    </button>
                    <button 
                      onClick={() => setCalendarView('week')}
                      className={`px-3 py-1 text-xs font-medium rounded-md transition-colors cursor-pointer whitespace-nowrap ${calendarView === 'week' ? 'text-teal-600 bg-teal-50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'}`}
                    >
                      周视图
                    </button>
                  </div>
                </div>

                {calendarView === 'week' ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-blue-50 border border-blue-100">
                      <div className="text-center">
                        <div className="text-xs text-blue-600 font-medium">周一</div>
                        <div className="text-lg font-bold text-blue-600">15</div>
                      </div>
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900">计算机网络 - 第5章授课</div>
                        <div className="text-xs text-gray-600 mt-1">10:00-11:40 · 教学楼A301</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-orange-50 border border-orange-100">
                      <div className="text-center">
                        <div className="text-xs text-orange-600 font-medium">周三</div>
                        <div className="text-lg font-bold text-orange-600">17</div>
                      </div>
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900">数据结构作业截止</div>
                        <div className="text-xs text-gray-600 mt-1">23:59 截止 · 已提交 45/68</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-green-50 border border-green-100">
                      <div className="text-center">
                        <div className="text-xs text-green-600 font-medium">周五</div>
                        <div className="text-lg font-bold text-green-600">19</div>
                      </div>
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900">在线答疑时段</div>
                        <div className="text-xs text-gray-600 mt-1">19:00-21:00 · 线上</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-purple-50 border border-purple-100">
                      <div className="text-center">
                        <div className="text-xs text-purple-600 font-medium">周日</div>
                        <div className="text-lg font-bold text-purple-600">21</div>
                      </div>
                      <div className="flex-1">
                        <div className="text-sm font-medium text-gray-900">操作系统期中考试</div>
                        <div className="text-xs text-gray-600 mt-1">14:00-16:00 · 教学楼B201</div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div>
                    {/* 月历头部 */}
                    <div className="flex items-center justify-between mb-4">
                      <button
                        onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1))}
                        className="w-7 h-7 flex items-center justify-center text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded cursor-pointer"
                      >
                        <i className="ri-arrow-left-s-line"></i>
                      </button>
                      <div className="text-sm font-semibold text-gray-900">
                        {currentMonth.getFullYear()}年{currentMonth.getMonth() + 1}月
                      </div>
                      <button
                        onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1))}
                        className="w-7 h-7 flex items-center justify-center text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded cursor-pointer"
                      >
                        <i className="ri-arrow-right-s-line"></i>
                      </button>
                    </div>

                    {/* 星期标题 */}
                    <div className="grid grid-cols-7 gap-1 mb-2">
                      {['日', '一', '二', '三', '四', '五', '六'].map((day, i) => (
                        <div key={i} className="text-center text-xs font-medium text-gray-500 py-1">
                          {day}
                        </div>
                      ))}
                    </div>

                    {/* 日期格子 */}
                    <div className="grid grid-cols-7 gap-1">
                      {generateMonthCalendar().map((week, weekIndex) => (
                        week.map((date, dayIndex) => {
                          const isCurrentMonth = date.getMonth() === currentMonth.getMonth();
                          const isToday = date.toDateString() === new Date().toDateString();
                          const events = getDateEvents(date);
                          
                          return (
                            <div
                              key={`${weekIndex}-${dayIndex}`}
                              className={`min-h-[60px] p-1 border border-gray-100 rounded cursor-pointer transition-colors ${
                                isCurrentMonth ? 'bg-white hover:bg-gray-50' : 'bg-gray-50'
                              } ${isToday ? 'ring-2 ring-teal-500' : ''}`}
                            >
                              <div className={`text-xs font-medium mb-1 ${
                                isCurrentMonth ? 'text-gray-900' : 'text-gray-400'
                              } ${isToday ? 'text-teal-600' : ''}`}>
                                {date.getDate()}
                              </div>
                              <div className="space-y-0.5">
                                {events.map((event, i) => (
                                  <div
                                    key={i}
                                    className={`text-xs px-1 py-0.5 rounded truncate ${
                                      event.color === 'blue' ? 'bg-blue-100 text-blue-700' :
                                      event.color === 'orange' ? 'bg-orange-100 text-orange-700' :
                                      event.color === 'green' ? 'bg-green-100 text-green-700' :
                                      'bg-purple-100 text-purple-700'
                                    }`}
                                    title={event.title}
                                  >
                                    {event.title}
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* 近期动态 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">近期动态</h2>
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-red-50 flex-shrink-0">
                      <i className="ri-alert-line text-red-600 text-base"></i>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900">系统预警</div>
                      <div className="text-xs text-gray-600 mt-1">计算机网络课程有12名学生连续3周未登录</div>
                      <div className="text-xs text-gray-400 mt-1">2小时前</div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-blue-50 flex-shrink-0">
                      <i className="ri-line-chart-line text-blue-600 text-base"></i>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900">提问趋势</div>
                      <div className="text-xs text-gray-600 mt-1">TCP拥塞控制相关问题激增,建议补充资料</div>
                      <div className="text-xs text-gray-400 mt-1">5小时前</div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-green-50 flex-shrink-0">
                      <i className="ri-download-line text-green-600 text-base"></i>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900">资料热度</div>
                      <div className="text-xs text-gray-600 mt-1">第5章PPT下载量达156次,为本周最高</div>
                      <div className="text-xs text-gray-400 mt-1">1天前</div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-purple-50 flex-shrink-0">
                      <i className="ri-thumb-up-line text-purple-600 text-base"></i>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900">AI表现优秀</div>
                      <div className="text-xs text-gray-600 mt-1">数据结构课程AI助教满意度达92%</div>
                      <div className="text-xs text-gray-400 mt-1">2天前</div>
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
              {[
                { id: 1, name: '计算机网络', code: 'CS301', students: 68, unread: 5, color: 'blue', image: 'https://readdy.ai/api/search-image?query=Modern%20computer%20network%20technology%20illustration%20with%20routers%20switches%20and%20data%20packets%20flowing%20through%20network%20infrastructure%2C%20clean%20minimalist%20background%20with%20soft%20blue%20tones%2C%20professional%20educational%20style%2C%20high%20quality%20digital%20art&width=400&height=240&seq=teacher-course-1&orientation=landscape' },
                { id: 2, name: '数据结构与算法', code: 'CS205', students: 82, unread: 12, color: 'green', image: 'https://readdy.ai/api/search-image?query=Abstract%20data%20structure%20visualization%20showing%20trees%20graphs%20and%20algorithms%20with%20geometric%20shapes%20and%20connecting%20lines%2C%20clean%20minimalist%20background%20with%20soft%20green%20tones%2C%20educational%20technology%20style%2C%20modern%20digital%20illustration&width=400&height=240&seq=teacher-course-2&orientation=landscape' },
                { id: 3, name: '操作系统原理', code: 'CS302', students: 56, unread: 3, color: 'purple', image: 'https://readdy.ai/api/search-image?query=Operating%20system%20concept%20illustration%20with%20process%20scheduling%20memory%20management%20and%20system%20architecture%20elements%2C%20clean%20minimalist%20background%20with%20soft%20purple%20tones%2C%20professional%20educational%20design%2C%20high%20quality%20digital%20art&width=400&height=240&seq=teacher-course-3&orientation=landscape' },
                { id: 4, name: '数据库系统', code: 'CS401', students: 74, unread: 8, color: 'orange', image: 'https://readdy.ai/api/search-image?query=Database%20system%20visualization%20with%20tables%20relationships%20and%20query%20processing%20elements%2C%20clean%20minimalist%20background%20with%20soft%20orange%20tones%2C%20modern%20educational%20technology%20style%2C%20professional%20digital%20illustration&width=400&height=240&seq=teacher-course-4&orientation=landscape' },
                { id: 5, name: '软件工程', code: 'CS403', students: 91, unread: 0, color: 'teal', image: 'https://readdy.ai/api/search-image?query=Software%20engineering%20concept%20with%20development%20lifecycle%20agile%20methodology%20and%20project%20management%20elements%2C%20clean%20minimalist%20background%20with%20soft%20teal%20tones%2C%20professional%20educational%20style%2C%20high%20quality%20digital%20art&width=400&height=240&seq=teacher-course-5&orientation=landscape' },
                { id: 6, name: '人工智能基础', code: 'CS501', students: 63, unread: 15, color: 'pink', image: 'https://readdy.ai/api/search-image?query=Artificial%20intelligence%20illustration%20with%20neural%20networks%20machine%20learning%20algorithms%20and%20AI%20technology%20elements%2C%20clean%20minimalist%20background%20with%20soft%20pink%20tones%2C%20modern%20educational%20design%2C%20professional%20digital%20art&width=400&height=240&seq=teacher-course-6&orientation=landscape' }
              ].map((course, index) => (
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
          <div className="max-w-3xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">个人设置</h1>
            
            <div className="space-y-5">
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">基本信息</h2>
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="relative">
                      {avatarPreview ? (
                        <img src={avatarPreview} alt="头像" className="w-16 h-16 rounded-full object-cover" />
                      ) : (
                        <div className="w-16 h-16 rounded-full bg-teal-500 flex items-center justify-center text-white text-xl font-medium">王</div>
                      )}
                      <input
                        type="file"
                        id="avatar-upload"
                        accept="image/*"
                        onChange={handleAvatarUpload}
                        className="hidden"
                      />
                    </div>
                    <label
                      htmlFor="avatar-upload"
                      className="px-4 py-2 text-sm font-medium text-teal-600 border border-teal-600 rounded-lg hover:bg-teal-50 transition-colors cursor-pointer whitespace-nowrap"
                    >
                      更换头像
                    </label>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">姓名</label>
                    <input 
                      type="text" 
                      value={profileForm.name}
                      onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" 
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">教学简介</label>
                    <textarea 
                      rows={3} 
                      value={profileForm.bio}
                      onChange={(e) => setProfileForm({ ...profileForm, bio: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" 
                      placeholder="介绍您的教学经历和研究方向..."
                    ></textarea>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">联系方式</label>
                    <input type="text" value={profileForm.email} onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })} className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">手机号码</label>
                    <input 
                      type="text" 
                      value={profileForm.phone}
                      onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                      placeholder="请输入手机号码"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" 
                    />
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">学校背景</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">所在学校</label>
                    <input 
                      type="text" 
                      value={profileForm.school}
                      onChange={(e) => setProfileForm({ ...profileForm, school: e.target.value })}
                      placeholder="请输入学校名称"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" 
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">所在学院</label>
                    <input 
                      type="text" 
                      value={profileForm.department}
                      onChange={(e) => setProfileForm({ ...profileForm, department: e.target.value })}
                      placeholder="请输入学院名称"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" 
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">职称</label>
                    <select 
                      value={profileForm.title}
                      onChange={(e) => setProfileForm({ ...profileForm, title: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 cursor-pointer"
                    >
                      <option value="">请选择职称</option>
                      <option value="助教">助教</option>
                      <option value="讲师">讲师</option>
                      <option value="副教授">副教授</option>
                      <option value="教授">教授</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">安全设置</h2>
                <div className="space-y-3">
                  <div className="flex items-center justify-between py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900">修改密码</div>
                      <div className="text-xs text-gray-500 mt-1">定期更换密码以保护账号安全</div>
                    </div>
                    <button 
                      onClick={() => setShowPasswordModal(true)}
                      className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap"
                    >
                      修改
                    </button>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900">登录设备管理</div>
                      <div className="text-xs text-gray-500 mt-1">查看和管理已登录的设备</div>
                    </div>
                    <button 
                      onClick={() => setShowDevicesModal(true)}
                      className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap"
                    >
                      查看
                    </button>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">偏好设置</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">默认AI对话风格</label>
                    <select className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 cursor-pointer">
                      <option>严谨学术型</option>
                      <option>启发引导型</option>
                      <option>Debug调试型</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">消息提醒方式</label>
                    <div className="space-y-2">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" defaultChecked className="w-4 h-4 text-teal-600 border-gray-300 rounded focus:ring-teal-500" />
                        <span className="text-sm text-gray-700">站内通知</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" defaultChecked className="w-4 h-4 text-teal-600 border-gray-300 rounded focus:ring-teal-500" />
                        <span className="text-sm text-gray-700">邮件提醒</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" className="w-4 h-4 text-teal-600 border-gray-300 rounded focus:ring-teal-500" />
                        <span className="text-sm text-gray-700">微信推送</span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              {/* 保存按钮 */}
              <div className="flex items-center justify-end gap-3">
                <button 
                  onClick={() => {
                    setProfileForm({
                      name: '王教授',
                      bio: '',
                      email: 'wang@university.edu.cn',
                      phone: '',
                      school: '',
                      department: '',
                      title: ''
                    });
                    setAvatarPreview('');
                  }}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
                >
                  重置
                </button>
                <button 
                  onClick={handleSaveProfile}
                  className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
                >
                  保存修改
                </button>
              </div>
            </div>
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
                    disabled={!newCourse.name || !newCourse.code || !newCourse.semester}
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
    </div>
  );
}