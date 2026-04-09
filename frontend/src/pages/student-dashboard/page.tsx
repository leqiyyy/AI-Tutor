import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

export default function StudentDashboard() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('learning');
  const [showJoinCourseModal, setShowJoinCourseModal] = useState(false);
  const [inviteCode, setInviteCode] = useState('');

  // 新增：通知中心相关状态
  const [notificationFilter, setNotificationFilter] = useState('all');
  const [notifications, setNotifications] = useState([
    { id: 1, type: 'deadline', title: '作业即将截止', content: '数据结构作业"第5章树与二叉树"将在3小时后截止提交', time: '刚刚', unread: true },
    { id: 2, type: 'reply', title: '教师回复了您的提问', content: '王教授回复了您关于"TCP三次握手"的提问', time: '1小时前', unread: true },
    { id: 3, type: 'exam', title: '考试提醒', content: '操作系统期中考试将于明天14:00在教学楼B201举行', time: '2小时前', unread: false },
    { id: 4, type: 'ai', title: 'AI学习建议', content: '检测到您在"TCP拥塞控制"知识点掌握度较低,建议重点复习', time: '5小时前', unread: false },
    { id: 5, type: 'material', title: '新资料发布', content: '计算机网络课程发布了新的学习资料"第6章应用层"', time: '1天前', unread: false }
  ]);

  // 新增：个人资料编辑相关状态
  const [showEditProfileModal, setShowEditProfileModal] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState('');
  const [profileForm, setProfileForm] = useState({
    name: '李明',
    studentId: '2021301234',
    email: 'liming@student.edu.cn',
    phone: '',
    school: '',
    college: '',
    major: '',
    grade: '',
    classNumber: ''
  });

  const handleJoinCourse = () => {
    if (inviteCode.trim()) {
      // 这里可以添加验证邀请码和加入课程的逻辑
      alert(`成功加入课程！邀请码：${inviteCode}`);
      setShowJoinCourseModal(false);
      setInviteCode('');
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
  };

  // 新增：标记单个通知为已读
  const markAsRead = (notificationId: number) => {
    setNotifications(prev => prev.map(n => 
      n.id === notificationId ? { ...n, unread: false } : n
    ));
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

  // 新增：保存个人资料
  const handleSaveProfile = () => {
    // 表单验证
    if (!profileForm.name.trim()) {
      alert('请输入姓名');
      return;
    }
    if (!profileForm.studentId.trim()) {
      alert('请输入学号');
      return;
    }
    if (!profileForm.email.trim()) {
      alert('请输入邮箱');
      return;
    }
    
    // 邮箱格式验证
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(profileForm.email)) {
      alert('请输入有效的邮箱地址');
      return;
    }
    
    // 手机号格式验证（如果填写了）
    if (profileForm.phone && !/^1[3-9]\d{9}$/.test(profileForm.phone)) {
      alert('请输入有效的手机号码');
      return;
    }
    
    // 这里应该调用后端API保存数据
    console.log('保存个人资料:', profileForm);
    console.log('头像预览:', avatarPreview);
    
    alert('个人资料保存成功！');
    setShowEditProfileModal(false);
  };

  return (
    <div className="min-h-screen bg-gray-50" translate="no">
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
                <button onClick={() => setActiveTab('profile')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'profile' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>个人中心</button>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="w-8 h-8 flex items-center justify-center text-gray-600 hover:text-gray-900 cursor-pointer">
                <i className="ri-notification-3-line text-lg"></i>
              </button>
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium cursor-pointer">李</div>
            </div>
          </div>
        </div>
      </nav>

      {/* 主内容区 */}
      <div className="pt-16 px-6 py-6">
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
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-red-50 border border-red-100">
                      <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-red-100 flex-shrink-0">
                        <i className="ri-alarm-warning-line text-red-600 text-base"></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">数据结构作业即将截止</div>
                        <div className="text-xs text-gray-600 mt-1">还剩 3 小时 · 第5章树与二叉树</div>
                      </div>
                      <button 
                        onClick={() => handleGoToHomework(2, 'hw-tree-binary')}
                        className="px-3 py-1.5 text-xs font-medium text-red-600 bg-red-100 rounded-md hover:bg-red-200 cursor-pointer whitespace-nowrap"
                      >
                        立即完成
                      </button>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-orange-50 border border-orange-100">
                      <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-orange-100 flex-shrink-0">
                        <i className="ri-file-list-3-line text-orange-600 text-base"></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">操作系统期中考试</div>
                        <div className="text-xs text-gray-600 mt-1">明天 14:00 · 教学楼B201</div>
                      </div>
                      <button 
                        onClick={() => handleGoToExam(3, 'exam-midterm-os')}
                        className="px-3 py-1.5 text-xs font-medium text-orange-600 bg-orange-100 rounded-md hover:bg-orange-200 cursor-pointer whitespace-nowrap"
                      >
                        查看详情
                      </button>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-blue-50 border border-blue-100">
                      <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-blue-100 flex-shrink-0">
                        <i className="ri-book-open-line text-blue-600 text-base"></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">复习TCP拥塞控制</div>
                        <div className="text-xs text-gray-600 mt-1">AI建议 · 该知识点掌握度较低</div>
                      </div>
                      <button 
                        onClick={() => handleGoToMaterial(1, 'chapter-5-tcp-congestion')}
                        className="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-100 rounded-md hover:bg-blue-200 cursor-pointer whitespace-nowrap"
                      >
                        开始学习
                      </button>
                    </div>
                  </div>
                </div>

                {/* 课程进度 */}
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">课程进度</h2>
                  <div className="space-y-4">
                    {[
                      { name: '计算机网络', progress: 68, chapter: '第5章 传输层', unread: 2, color: 'blue' },
                      { name: '数据结构与算法', progress: 82, chapter: '第7章 图', unread: 5, color: 'green' },
                      { name: '操作系统原理', progress: 56, chapter: '第4章 内存管理', unread: 1, color: 'purple' }
                    ].map((course, index) => (
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
                            <div className={`h-full bg-${course.color}-500 rounded-full`} style={{ width: `${course.progress}%` }}></div>
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
                    <div className="p-3 rounded-lg bg-purple-50">
                      <div className="text-sm font-medium text-gray-900 mb-1">TCP拥塞控制需复习</div>
                      <div className="text-xs text-gray-600">该知识点最近提问3次,建议重点复习</div>
                    </div>
                    <div className="p-3 rounded-lg bg-blue-50">
                      <div className="text-sm font-medium text-gray-900 mb-1">红黑树掌握良好</div>
                      <div className="text-xs text-gray-600">相关练习正确率达90%,继续保持</div>
                    </div>
                    <div className="p-3 rounded-lg bg-green-50">
                      <div className="text-sm font-medium text-gray-900 mb-1">建议学习图的遍历</div>
                      <div className="text-xs text-gray-600">下周将学习该内容,可提前预习</div>
                    </div>
                  </div>
                </div>

                {/* 学习动态 */}
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">学习动态</h2>
                  <div className="space-y-3">
                    <div className="flex items-start gap-2">
                      <div className="w-6 h-6 flex items-center justify-center rounded-full bg-green-50 flex-shrink-0">
                        <i className="ri-file-text-line text-green-600 text-xs"></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-900">王教授上传了新资料</div>
                        <div className="text-xs text-gray-500 mt-1">计算机网络 · 2小时前</div>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <div className="w-6 h-6 flex items-center justify-center rounded-full bg-blue-50 flex-shrink-0">
                        <i className="ri-trophy-line text-blue-600 text-xs"></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-900">同学获得满分成就</div>
                        <div className="text-xs text-gray-500 mt-1">数据结构 · 5小时前</div>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <div className="w-6 h-6 flex items-center justify-center rounded-full bg-orange-50 flex-shrink-0">
                        <i className="ri-chat-3-line text-orange-600 text-xs"></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-900">教师发布集中答疑</div>
                        <div className="text-xs text-gray-500 mt-1">操作系统 · 1天前</div>
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
                onClick={() => setShowJoinCourseModal(true)}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap"
              >
                <i className="ri-add-line mr-1"></i>加入课程
              </button>
            </div>

            <div className="grid grid-cols-3 gap-5" translate="no">
              {[
                { id: 1, name: '计算机网络', teacher: '王教授', progress: 68, unread: 2, image: 'https://readdy.ai/api/search-image?query=Modern%20computer%20network%20technology%20illustration%20with%20routers%20switches%20and%20data%20packets%20flowing%20through%20network%20infrastructure%2C%20clean%20minimalist%20background%20with%20soft%20blue%20tones%2C%20professional%20educational%20style%2C%20high%20quality%20digital%20art&width=400&height=240&seq=student-course-1&orientation=landscape' },
                { id: 2, name: '数据结构与算法', teacher: '李教授', progress: 82, unread: 5, image: 'https://readdy.ai/api/search-image?query=Abstract%20data%20structure%20visualization%20showing%20trees%20graphs%20and%20algorithms%20with%20geometric%20shapes%20and%20connecting%20lines%2C%20clean%20minimalist%20background%20with%20soft%20green%20tones%2C%20educational%20technology%20style%2C%20modern%20digital%20illustration&width=400&height=240&seq=student-course-2&orientation=landscape' },
                { id: 3, name: '操作系统原理', teacher: '张教授', progress: 56, unread: 1, image: 'https://readdy.ai/api/search-image?query=Operating%20system%20concept%20illustration%20with%20process%20scheduling%20memory%20management%20and%20system%20architecture%20elements%2C%20clean%20minimalist%20background%20with%20soft%20purple%20tones%2C%20professional%20educational%20design%2C%20high%20quality%20digital%20art&width=400&height=240&seq=student-course-3&orientation=landscape' },
                { id: 4, name: '数据库系统', teacher: '刘教授', progress: 45, unread: 3, image: 'https://readdy.ai/api/search-image?query=Database%20system%20visualization%20with%20tables%20relationships%20and%20query%20processing%20elements%2C%20clean%20minimalist%20background%20with%20soft%20orange%20tones%2C%20modern%20educational%20technology%20style%2C%20professional%20digital%20illustration&width=400&height=240&seq=student-course-4&orientation=landscape' },
                { id: 5, name: '软件工程', teacher: '陈教授', progress: 91, unread: 0, image: 'https://readdy.ai/api/search-image?query=Software%20engineering%20concept%20with%20development%20lifecycle%20agile%20methodology%20and%20project%20management%20elements%2C%20clean%20minimalist%20background%20with%20soft%20teal%20tones%2C%20professional%20educational%20style%2C%20high%20quality%20digital%20art&width=400&height=240&seq=student-course-5&orientation=landscape' }
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
            <h1 className="text-2xl font-bold text-gray-900 mb-6">个人中心</h1>
            
            <div className="grid grid-cols-3 gap-6">
              <div className="col-span-2 space-y-5">
                {/* 能力雷达图 */}
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">个人能力分析</h2>
                  <div className="flex items-center justify-center py-8">
                    <div className="relative w-64 h-64">
                      <svg viewBox="0 0 200 200" className="w-full h-full">
                        <polygon points="100,20 170,60 170,140 100,180 30,140 30,60" fill="#f0fdfa" stroke="#14b8a6" strokeWidth="1" opacity="0.3"/>
                        <polygon points="100,50 145,75 145,125 100,150 55,125 55,75" fill="#14b8a6" opacity="0.5"/>
                        <line x1="100" y1="100" x2="100" y2="20" stroke="#e5e7eb" strokeWidth="1"/>
                        <line x1="100" y1="100" x2="170" y2="60" stroke="#e5e7eb" strokeWidth="1"/>
                        <line x1="100" y1="100" x2="170" y2="140" stroke="#e5e7eb" strokeWidth="1"/>
                        <line x1="100" y1="100" x2="100" y2="180" stroke="#e5e7eb" strokeWidth="1"/>
                        <line x1="100" y1="100" x2="30" y2="140" stroke="#e5e7eb" strokeWidth="1"/>
                        <line x1="100" y1="100" x2="30" y2="60" stroke="#e5e7eb" strokeWidth="1"/>
                        <text x="100" y="15" textAnchor="middle" className="text-xs fill-gray-600">理论知识</text>
                        <text x="175" y="65" textAnchor="start" className="text-xs fill-gray-600">编程能力</text>
                        <text x="175" y="145" textAnchor="start" className="text-xs fill-gray-600">协议理解</text>
                        <text x="100" y="195" textAnchor="middle" className="text-xs fill-gray-600">算法设计</text>
                        <text x="20" y="145" textAnchor="end" className="text-xs fill-gray-600">系统架构</text>
                        <text x="20" y="65" textAnchor="end" className="text-xs fill-gray-600">数据库</text>
                      </svg>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mt-4">
                    <div className="text-center p-3 rounded-lg bg-teal-50">
                      <div className="text-lg font-bold text-teal-600">85</div>
                      <div className="text-xs text-gray-600 mt-1">理论知识</div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-blue-50">
                      <div className="text-lg font-bold text-blue-600">78</div>
                      <div className="text-xs text-gray-600 mt-1">编程能力</div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-green-50">
                      <div className="text-lg font-bold text-green-600">72</div>
                      <div className="text-xs text-gray-600 mt-1">协议理解</div>
                    </div>
                  </div>
                </div>

                {/* 学习日历热力图 */}
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">学习日历</h2>
                  <div className="space-y-2">
                    {[0, 1, 2, 3, 4, 5, 6].map((week) => (
                      <div key={week} className="flex items-center gap-1">
                        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30].map((day) => {
                          const intensity = Math.floor(Math.random() * 5);
                          return (
                            <div key={day} className={`w-3 h-3 rounded-sm ${
                              intensity === 0 ? 'bg-gray-100' :
                              intensity === 1 ? 'bg-teal-100' :
                              intensity === 2 ? 'bg-teal-200' :
                              intensity === 3 ? 'bg-teal-400' :
                              'bg-teal-600'
                            }`} title={`${intensity}小时`}></div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center justify-between mt-4 text-xs text-gray-500">
                    <span>最近7个月学习活跃度</span>
                    <div className="flex items-center gap-2">
                      <span>少</span>
                      <div className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded-sm bg-gray-100"></div>
                        <div className="w-3 h-3 rounded-sm bg-teal-100"></div>
                        <div className="w-3 h-3 rounded-sm bg-teal-200"></div>
                        <div className="w-3 h-3 rounded-sm bg-teal-400"></div>
                        <div className="w-3 h-3 rounded-sm bg-teal-600"></div>
                      </div>
                      <span>多</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 右侧统计 */}
              <div className="space-y-5">
                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">学习统计</h2>
                  <div className="space-y-4">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-600">本周学习时长</span>
                        <span className="text-sm font-semibold text-gray-900">18.5小时</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-teal-500 rounded-full" style={{ width: '74%' }}></div>
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-600">作业完成率</span>
                        <span className="text-sm font-semibold text-gray-900">92%</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-green-500 rounded-full" style={{ width: '92%' }}></div>
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-600">AI提问次数</span>
                        <span className="text-sm font-semibold text-gray-900">47次</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: '65%' }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">提问关键词</h2>
                  <div className="flex flex-wrap gap-2">
                    {['TCP', '红黑树', '进程调度', '索引', '拥塞控制', '二叉树', '死锁', 'SQL', '路由算法', '哈希表', '虚拟内存', '事务'].map((keyword, index) => (
                      <span key={index} className="px-3 py-1 text-xs font-medium text-gray-700 bg-gray-100 rounded-full">{keyword}</span>
                    ))}
                  </div>
                </div>

                <div className="bg-white rounded-lg p-5 border border-gray-200">
                  <h2 className="text-base font-semibold text-gray-900 mb-4">个人资料</h2>
                  <div className="space-y-3">
                    <div className="flex items-center justify-center mb-4">
                      {avatarPreview ? (
                        <img src={avatarPreview} alt="头像" className="w-20 h-20 rounded-full object-cover" />
                      ) : (
                        <div className="w-20 h-20 rounded-full bg-blue-500 flex items-center justify-center text-white text-2xl font-medium">李</div>
                      )}
                    </div>
                    <div>
                      <div className="text-xs text-gray-500 mb-1">姓名</div>
                      <div className="text-sm text-gray-900">{profileForm.name}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500 mb-1">学号</div>
                      <div className="text-sm text-gray-900">{profileForm.studentId}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500 mb-1">院系</div>
                      <div className="text-sm text-gray-900">{profileForm.college || '计算机学院'}</div>
                    </div>
                    <button 
                      onClick={() => setShowEditProfileModal(true)}
                      className="w-full mt-4 px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap"
                    >
                      编辑资料
                    </button>
                  </div>
                </div>
              </div>
            </div>
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
                  placeholder="请输入6位邀请码" 
                  maxLength={6}
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
                disabled={inviteCode.length !== 6}
                className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
              >
                加入课程
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 编辑个人资料弹窗 */}
      {showEditProfileModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
              <h2 className="text-lg font-semibold text-gray-900">编辑个人资料</h2>
            </div>
            
            <div className="px-6 py-5 overflow-y-auto flex-1">
              <div className="space-y-5">
                {/* 头像上传 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">头像</label>
                  <div className="flex items-center gap-4">
                    <div className="relative">
                      {avatarPreview ? (
                        <img src={avatarPreview} alt="头像预览" className="w-20 h-20 rounded-full object-cover" />
                      ) : (
                        <div className="w-20 h-20 rounded-full bg-blue-500 flex items-center justify-center text-white text-2xl font-medium">
                          {profileForm.name[0]}
                        </div>
                      )}
                      <input
                        type="file"
                        id="avatar-upload"
                        accept="image/*"
                        onChange={handleAvatarUpload}
                        className="hidden"
                      />
                    </div>
                    <div className="flex flex-col gap-2">
                      <label
                        htmlFor="avatar-upload"
                        className="px-4 py-2 text-sm font-medium text-teal-600 border border-teal-600 rounded-lg hover:bg-teal-50 transition-colors cursor-pointer whitespace-nowrap inline-block"
                      >
                        更换头像
                      </label>
                      <p className="text-xs text-gray-500">支持JPG、PNG格式，文件小于2MB</p>
                    </div>
                  </div>
                </div>

                {/* 基本信息 */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">基本信息</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">姓名 *</label>
                      <input
                        type="text"
                        value={profileForm.name}
                        onChange={(e) => setProfileForm({ ...profileForm, name: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="请输入姓名"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">学号 *</label>
                      <input
                        type="text"
                        value={profileForm.studentId}
                        onChange={(e) => setProfileForm({ ...profileForm, studentId: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="请输入学号"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">邮箱 *</label>
                      <input
                        type="email"
                        value={profileForm.email}
                        onChange={(e) => setProfileForm({ ...profileForm, email: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="请输入邮箱"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">手机号</label>
                      <input
                        type="tel"
                        value={profileForm.phone}
                        onChange={(e) => setProfileForm({ ...profileForm, phone: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="请输入手机号"
                      />
                    </div>
                  </div>
                </div>

                {/* 学校信息 */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">学校信息</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">学校</label>
                      <input
                        type="text"
                        value={profileForm.school}
                        onChange={(e) => setProfileForm({ ...profileForm, school: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="请输入学校名称"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">学院</label>
                      <input
                        type="text"
                        value={profileForm.college}
                        onChange={(e) => setProfileForm({ ...profileForm, college: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="请输入学院名称"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">专业</label>
                      <input
                        type="text"
                        value={profileForm.major}
                        onChange={(e) => setProfileForm({ ...profileForm, major: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="请输入专业名称"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">年级</label>
                      <select
                        value={profileForm.grade}
                        onChange={(e) => setProfileForm({ ...profileForm, grade: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 cursor-pointer"
                      >
                        <option value="">请选择年级</option>
                        <option value="2024">2024级</option>
                        <option value="2023">2023级</option>
                        <option value="2022">2022级</option>
                        <option value="2021">2021级</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">班级编号</label>
                      <input
                        type="text"
                        value={profileForm.classNumber}
                        onChange={(e) => setProfileForm({ ...profileForm, classNumber: e.target.value })}
                        className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        placeholder="例如：01班"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3 flex-shrink-0">
              <button
                onClick={() => {
                  setShowEditProfileModal(false);
                  setAvatarPreview('');
                }}
                className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap"
              >
                取消
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
  );
}