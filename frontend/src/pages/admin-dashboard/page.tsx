import { useState, useRef, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ProductSidePanel from '../../components/ProductSidePanel';
import { authService } from '@/services/auth';
import { adminService } from '@/services/admin';
import { dashboardService } from '@/services/dashboard';
import type {
  AdminAuditAnswer,
  AdminAuditReport,
  AdminCourseRow,
  AdminDashboardData,
  AdminUserReview,
  AdminUserRow,
} from '@/types/dashboard';

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [dashboardData, setDashboardData] = useState<AdminDashboardData | null>(null);
  const [dashboardError, setDashboardError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [actionPending, setActionPending] = useState(false);
  const [userReviews, setUserReviews] = useState<AdminUserReview[]>([]);
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [courses, setCourses] = useState<AdminCourseRow[]>([]);
  const [auditAnswers, setAuditAnswers] = useState<AdminAuditAnswer[]>([]);
  const [auditReports, setAuditReports] = useState<AdminAuditReport[]>([]);
  const [sensitiveWords, setSensitiveWords] = useState<string[]>([]);
  const [newSensitiveWord, setNewSensitiveWord] = useState('');
  const [systemSettings, setSystemSettings] = useState({
    maintenanceMode: false,
    examWeekLimit: true,
    backupSchedule: '每天 23:00',
    announcementTitle: '',
    announcementContent: '',
    announcementAudience: '全校师生',
  });
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
      .getAdminDashboard()
      .then((data) => {
        if (!mounted) return;
        setDashboardData(data);
        setUserReviews(data.userReviews);
        setUsers(data.users);
        setCourses(data.courses);
        setAuditAnswers(data.auditAnswers);
        setAuditReports(data.auditReports);
        setSensitiveWords(data.sensitiveWords);
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

  const showActionMessage = (message: string) => {
    setActionMessage(message);
    window.setTimeout(() => setActionMessage(''), 2500);
  };

  const runAdminAction = async (action: () => Promise<void>, successMessage: string) => {
    try {
      setActionPending(true);
      setDashboardError('');
      await action();
      showActionMessage(successMessage);
    } catch (error) {
      setDashboardError(error instanceof Error ? error.message : '操作失败，请稍后重试');
    } finally {
      setActionPending(false);
    }
  };

  const handleReviewRegistration = async (userId: string, decision: 'approve' | 'reject') => {
    await runAdminAction(
      async () => {
        await adminService.reviewRegistration({ userId, decision });
        setUserReviews((prev) => prev.filter((item) => item.id !== userId));
      },
      decision === 'approve' ? '已通过注册申请' : '已拒绝注册申请',
    );
  };

  const handleBatchReviewRegistrations = async (decision: 'approve' | 'reject') => {
    if (userReviews.length === 0) {
      return;
    }

    await runAdminAction(
      async () => {
        await Promise.all(
          userReviews.map((item) =>
            adminService.reviewRegistration({ userId: item.id, decision }),
          ),
        );
        setUserReviews([]);
      },
      decision === 'approve' ? '已批量通过注册申请' : '已批量拒绝注册申请',
    );
  };

  const handleToggleUserStatus = async (user: AdminUserRow) => {
    const nextStatus = user.status === 'disabled' ? 'enabled' : 'disabled';

    await runAdminAction(
      async () => {
        await adminService.updateUserStatus({ userId: user.id, status: nextStatus });
        setUsers((prev) =>
          prev.map((item) =>
            item.id === user.id
              ? {
                  ...item,
                  status: nextStatus === 'disabled' ? 'disabled' : 'offline',
                  statusLabel: nextStatus === 'disabled' ? '已禁用' : '离线',
                }
              : item,
          ),
        );
      },
      nextStatus === 'disabled' ? '用户已禁用' : '用户已恢复启用',
    );
  };

  const handleArchiveCourse = async (courseId: string) => {
    await runAdminAction(
      async () => {
        await adminService.updateCourseStatus({ courseId, status: 'archived' });
        setCourses((prev) => prev.filter((item) => item.id !== courseId));
      },
      '课程已归档',
    );
  };

  const handleReviewAnswer = async (itemId: string) => {
    await runAdminAction(
      async () => {
        await adminService.reviewContent({ itemId, decision: 'markIncorrect' });
        setAuditAnswers((prev) => prev.filter((item) => item.id !== itemId));
      },
      '已标记 AI 回答错误',
    );
  };

  const handleResolveReport = async (reportId: string, decision: 'delete' | 'reject') => {
    await runAdminAction(
      async () => {
        await adminService.reviewContent({ itemId: reportId, decision });
        setAuditReports((prev) => prev.filter((item) => item.id !== reportId));
      },
      decision === 'delete' ? '已删除被举报内容' : '已驳回举报',
    );
  };

  const handleSaveSystemSettings = async () => {
    await runAdminAction(
      async () => {
        await adminService.updateSystemSettings({
          maintenanceMode: systemSettings.maintenanceMode,
          examWeekLimit: systemSettings.examWeekLimit,
          backupSchedule: systemSettings.backupSchedule,
          announcement: systemSettings.announcementTitle || systemSettings.announcementContent
            ? {
                title: systemSettings.announcementTitle,
                content: systemSettings.announcementContent,
                audience: systemSettings.announcementAudience,
              }
            : undefined,
        });
      },
      '系统设置已保存',
    );
  };

  const handlePublishAnnouncement = async () => {
    if (!systemSettings.announcementTitle.trim() || !systemSettings.announcementContent.trim()) {
      setDashboardError('请填写完整的公告标题和内容');
      return;
    }

    await runAdminAction(
      async () => {
        await adminService.updateSystemSettings({
          announcement: {
            title: systemSettings.announcementTitle.trim(),
            content: systemSettings.announcementContent.trim(),
            audience: systemSettings.announcementAudience,
          },
        });
        setSystemSettings((prev) => ({
          ...prev,
          announcementTitle: '',
          announcementContent: '',
        }));
      },
      '系统公告已发布',
    );
  };

  const handleAddSensitiveWord = () => {
    const value = newSensitiveWord.trim();
    if (!value || sensitiveWords.includes(value)) {
      return;
    }
    setSensitiveWords((prev) => [...prev, value]);
    setNewSensitiveWord('');
  };

  const handleRemoveSensitiveWord = (word: string) => {
    setSensitiveWords((prev) => prev.filter((item) => item !== word));
  };

  const adminStats = dashboardData?.stats ?? [];
  const adminActivities = dashboardData?.activities ?? [];
  const adminTodoReminders = dashboardData?.todoReminders ?? [];
  const adminSystemStatus = dashboardData?.systemStatus ?? [];

  return (
    <div className="soft-dash soft-dash-admin min-h-screen bg-gray-50">
      {/* 固定导航栏 */}
      <nav className="fixed top-0 left-0 right-0 bg-white border-b border-gray-200 z-50">
        <div className="px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-2">
                <img src="https://public.readdy.ai/ai/img_res/2625f127-2f4f-41ee-82d8-6c2fa4dee4ac.png" alt="珞樱学堂" className="h-9 w-9" />
                <span className="text-lg font-semibold text-gray-900">珞樱学堂 · 管理端</span>
              </Link>
              <div className="flex items-center gap-1">
                <button onClick={() => setActiveTab('overview')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'overview' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>系统概览</button>
                <button onClick={() => setActiveTab('users')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'users' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>用户管理</button>
                <button onClick={() => setActiveTab('courses')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'courses' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>课程管理</button>
                <button onClick={() => setActiveTab('audit')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors relative ${activeTab === 'audit' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>
                  内容审核
                  <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
                </button>
                <button onClick={() => setActiveTab('settings')} className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${activeTab === 'settings' ? 'bg-teal-50 text-teal-600' : 'text-gray-600 hover:text-gray-900'}`}>系统设置</button>
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
                  <div className="w-8 h-8 rounded-full bg-teal-600 flex items-center justify-center text-white text-sm font-medium">管</div>
                  <span className="text-sm text-gray-700 font-medium">超级管理员</span>
                  <i className={`ri-arrow-down-s-line text-gray-400 text-base transition-transform ${showUserMenu ? 'rotate-180' : ''}`}></i>
                </button>
                {showUserMenu && (
                  <div className="absolute right-0 bottom-full mb-1.5 w-44 origin-bottom-right bg-white border border-gray-200 rounded-xl overflow-hidden z-50">
                    <div className="px-4 py-3 border-b border-gray-100">
                      <div className="text-sm font-semibold text-gray-900">超级管理员</div>
                      <div className="text-xs text-gray-500 mt-0.5">admin@university.edu.cn</div>
                    </div>
                    <div className="py-1">
                      <button
                        onClick={() => { setActiveTab('settings'); setShowUserMenu(false); }}
                        className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer"
                      >
                        <i className="ri-settings-3-line text-gray-400 text-base"></i>
                        系统设置
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
        {actionMessage && (
          <div className="max-w-7xl mx-auto mb-4 rounded-lg border border-teal-100 bg-teal-50 px-4 py-3 text-sm text-teal-700">
            {actionMessage}
          </div>
        )}
        {activeTab === 'overview' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">系统概览</h1>
            
            {/* 基础数据 */}
            <div className="grid grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">注册教师</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-blue-50">
                    <i className="ri-user-star-line text-blue-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">{adminStats[0]?.value ?? '156'}</div>
                <div className="text-xs text-green-600 mt-1">+8 本月</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">注册学生</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-green-50">
                    <i className="ri-group-line text-green-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">{adminStats[1]?.value ?? '3,842'}</div>
                <div className="text-xs text-green-600 mt-1">+127 本月</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">开设课程</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-purple-50">
                    <i className="ri-book-open-line text-purple-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">{adminStats[2]?.value ?? '284'}</div>
                <div className="text-xs text-gray-500 mt-1">本学期</div>
              </div>
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">活跃班级</span>
                  <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-orange-50">
                    <i className="ri-team-line text-orange-600 text-base"></i>
                  </div>
                </div>
                <div className="text-2xl font-bold text-gray-900">{adminStats[3]?.value ?? '218'}</div>
                <div className="text-xs text-gray-500 mt-1">近7天活跃</div>
              </div>
            </div>

            {/* 待办提醒 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200 mb-6">
              <h2 className="text-base font-semibold text-gray-900 mb-4">待办提醒</h2>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-red-50 border border-red-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">{adminTodoReminders[0]?.title ?? '待审核注册'}</span>
                    <div className="w-7 h-7 flex items-center justify-center rounded-full bg-red-500 text-white text-xs font-bold">{adminTodoReminders[0]?.count ?? 0}</div>
                  </div>
                  <div className="text-xs text-gray-600">{adminTodoReminders[0]?.content ?? '教师资质审核 8 人 · 学生学籍核验 4 人'}</div>
                  <button onClick={() => setActiveTab('users')} className="mt-3 w-full px-3 py-1.5 text-xs font-medium text-red-600 bg-red-100 rounded-md hover:bg-red-200 cursor-pointer whitespace-nowrap">{adminTodoReminders[0]?.actionLabel ?? '立即处理'}</button>
                </div>
                <div className="p-4 rounded-lg bg-orange-50 border border-orange-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">{adminTodoReminders[1]?.title ?? '知识库异常'}</span>
                    <div className="w-7 h-7 flex items-center justify-center rounded-full bg-orange-500 text-white text-xs font-bold">{adminTodoReminders[1]?.count ?? 0}</div>
                  </div>
                  <div className="text-xs text-gray-600">{adminTodoReminders[1]?.content ?? '索引构建失败 3 个 · 资料解析错误 2 个'}</div>
                  <button onClick={() => setActiveTab('courses')} className="mt-3 w-full px-3 py-1.5 text-xs font-medium text-orange-600 bg-orange-100 rounded-md hover:bg-orange-200 cursor-pointer whitespace-nowrap">{adminTodoReminders[1]?.actionLabel ?? '查看详情'}</button>
                </div>
                <div className="p-4 rounded-lg bg-blue-50 border border-blue-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-900">{adminTodoReminders[2]?.title ?? '待处理举报'}</span>
                    <div className="w-7 h-7 flex items-center justify-center rounded-full bg-blue-500 text-white text-xs font-bold">{adminTodoReminders[2]?.count ?? 0}</div>
                  </div>
                  <div className="text-xs text-gray-600">{adminTodoReminders[2]?.content ?? '内容举报 2 条 · AI回答错误 1 条'}</div>
                  <button onClick={() => setActiveTab('audit')} className="mt-3 w-full px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-100 rounded-md hover:bg-blue-200 cursor-pointer whitespace-nowrap">{adminTodoReminders[2]?.actionLabel ?? '前往审核'}</button>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              {/* 近期动态 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">近期动态</h2>
                <div className="space-y-3">
                  {adminActivities.map((activity, index) => (
                    <div key={index} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50">
                      <div className={`w-8 h-8 flex items-center justify-center rounded-lg bg-${activity.color}-50 flex-shrink-0`}>
                        <i className={`text-base ${
                          activity.type === 'user' ? `ri-user-add-line text-${activity.color}-600` :
                          activity.type === 'course' ? `ri-book-line text-${activity.color}-600` :
                          activity.type === 'announcement' ? `ri-megaphone-line text-${activity.color}-600` :
                          `ri-save-line text-${activity.color}-600`
                        }`}></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">{activity.title}</div>
                        <div className="text-xs text-gray-600 mt-1">{activity.content}</div>
                        <div className="text-xs text-gray-400 mt-1">{activity.time}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 系统状态 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">系统状态</h2>
                <div className="space-y-4">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">{adminSystemStatus[0]?.label ?? '服务器负载'}</span>
                      <span className="text-sm font-semibold text-green-600">{adminSystemStatus[0]?.status ?? '正常'}</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-green-500 rounded-full" style={{ width: `${adminSystemStatus[0]?.progress ?? 35}%` }}></div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">{adminSystemStatus[0]?.detail ?? 'CPU: 35% · 内存: 42%'}</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">{adminSystemStatus[1]?.label ?? '数据库状态'}</span>
                      <span className="text-sm font-semibold text-green-600">{adminSystemStatus[1]?.status ?? '运行中'}</span>
                    </div>
                    <div className="text-xs text-gray-500">{adminSystemStatus[1]?.detail ?? '连接数: 156/500 · 响应时间: 12ms'}</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">{adminSystemStatus[2]?.label ?? 'AI服务状态'}</span>
                      <span className="text-sm font-semibold text-green-600">{adminSystemStatus[2]?.status ?? '正常'}</span>
                    </div>
                    <div className="text-xs text-gray-500">{adminSystemStatus[2]?.detail ?? '今日调用: 8,234 次 · 平均响应: 1.2s'}</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">{adminSystemStatus[3]?.label ?? '存储空间'}</span>
                      <span className="text-sm font-semibold text-orange-600">{adminSystemStatus[3]?.status ?? '68%'}</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-orange-500 rounded-full" style={{ width: `${adminSystemStatus[3]?.progress ?? 68}%` }}></div>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">{adminSystemStatus[3]?.detail ?? '已用 680GB / 总计 1TB'}</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">{adminSystemStatus[4]?.label ?? '最近备份'}</span>
                      <span className="text-sm font-semibold text-gray-900">{adminSystemStatus[4]?.status ?? '5小时前'}</span>
                    </div>
                    <div className="text-xs text-gray-500">{adminSystemStatus[4]?.detail ?? '下次自动备份: 今天 23:00'}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'users' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">用户管理</h1>
            
            {/* 注册审核 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-900">注册审核</h2>
                <div className="flex items-center gap-2">
                  <button onClick={() => handleBatchReviewRegistrations('approve')} disabled={actionPending || userReviews.length === 0} className="px-3 py-1.5 text-sm font-medium text-green-600 border border-green-600 rounded-lg hover:bg-green-50 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">批量通过</button>
                  <button onClick={() => handleBatchReviewRegistrations('reject')} disabled={actionPending || userReviews.length === 0} className="px-3 py-1.5 text-sm font-medium text-red-600 border border-red-600 rounded-lg hover:bg-red-50 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">批量拒绝</button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">
                        <input type="checkbox" className="w-4 h-4 text-teal-600 border-gray-300 rounded" />
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">姓名</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">角色</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">院系</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">工号/学号</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">申请时间</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {userReviews.map((user) => (
                      <tr key={user.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <input type="checkbox" className="w-4 h-4 text-teal-600 border-gray-300 rounded" />
                        </td>
                        <td className="px-4 py-3 font-medium text-gray-900">{user.name}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${user.role === 'teacher' ? 'bg-blue-50 text-blue-600' : 'bg-green-50 text-green-600'}`}>
                            {user.roleLabel}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-600">{user.department}</td>
                        <td className="px-4 py-3 text-gray-600 font-mono text-xs">{user.accountNo}</td>
                        <td className="px-4 py-3 text-gray-500">{user.appliedAt}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button onClick={() => handleReviewRegistration(user.id, 'approve')} disabled={actionPending} className="px-3 py-1 text-xs font-medium text-green-600 bg-green-50 rounded-md hover:bg-green-100 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">通过</button>
                            <button onClick={() => handleReviewRegistration(user.id, 'reject')} disabled={actionPending} className="px-3 py-1 text-xs font-medium text-red-600 bg-red-50 rounded-md hover:bg-red-100 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">拒绝</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* 用户列表 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-900">用户列表</h2>
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <input type="text" placeholder="搜索用户..." className="w-64 pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
                    <i className="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
                  </div>
                  <select className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                    <option>全部角色</option>
                    <option>教师</option>
                    <option>学生</option>
                    <option>管理员</option>
                  </select>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">姓名</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">角色</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">院系</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">注册时间</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">登录状态</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {users.map((user) => (
                      <tr key={user.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{user.name}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${user.role === 'teacher' ? 'bg-blue-50 text-blue-600' : user.role === 'admin' ? 'bg-purple-50 text-purple-600' : 'bg-green-50 text-green-600'}`}>
                            {user.roleLabel}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-600">{user.department}</td>
                        <td className="px-4 py-3 text-gray-600">{user.registeredAt}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1 text-xs ${user.status === 'online' ? 'text-green-600' : user.status === 'disabled' ? 'text-red-600' : 'text-gray-500'}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${user.status === 'online' ? 'bg-green-500' : user.status === 'disabled' ? 'bg-red-500' : 'bg-gray-400'}`}></span>
                            {user.statusLabel}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">查看</button>
                            <button className="text-xs text-gray-600 hover:text-gray-700 cursor-pointer whitespace-nowrap">重置密码</button>
                            <button onClick={() => handleToggleUserStatus(user)} disabled={actionPending} className={`text-xs cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed ${user.status === 'disabled' ? 'text-green-600 hover:text-green-700' : 'text-red-600 hover:text-red-700'}`}>{user.status === 'disabled' ? '启用' : '禁用'}</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'courses' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">课程管理</h1>
            
            <div className="bg-white rounded-lg p-5 border border-gray-200">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-900">课程总览</h2>
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <input type="text" placeholder="搜索课程..." className="w-64 pl-9 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
                    <i className="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"></i>
                  </div>
                  <select className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                    <option>全部学院</option>
                    <option>计算机学院</option>
                    <option>软件学院</option>
                    <option>信息学院</option>
                  </select>
                  <select className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                    <option>本学期</option>
                    <option>上学期</option>
                    <option>全部学期</option>
                  </select>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">课程名称</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">授课教师</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">学生人数</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">知识库状态</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">最后活跃</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-600">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {courses.map((course) => (
                      <tr key={course.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{course.name}</td>
                        <td className="px-4 py-3 text-gray-600">{course.teacher}</td>
                        <td className="px-4 py-3 text-gray-600">{course.students} 人</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${course.knowledgeBaseStatus === 'normal' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                              {course.knowledgeBaseStatusLabel}
                            </span>
                            <span className="text-xs text-gray-500">{course.documentCount} 份资料</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-500">{course.lastActive}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button className="text-xs text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">查看详情</button>
                            <button className="text-xs text-gray-600 hover:text-gray-700 cursor-pointer whitespace-nowrap">转移负责人</button>
                            <button onClick={() => handleArchiveCourse(course.id)} disabled={actionPending} className="text-xs text-orange-600 hover:text-orange-700 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">归档</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="max-w-7xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">内容审核</h1>
            
            <div className="grid grid-cols-2 gap-6">
              {/* AI回答抽检 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">AI回答抽检</h2>
                <div className="space-y-3">
                  {auditAnswers.map((item) => (
                    <div key={item.id} className="p-4 rounded-lg border border-gray-200 hover:border-gray-300">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900 mb-1">{item.question}</div>
                          <div className="text-xs text-gray-600 line-clamp-2">{item.answer}</div>
                        </div>
                        <span className="ml-3 px-2 py-1 text-xs font-medium bg-red-50 text-red-600 rounded-full flex-shrink-0">
                          {item.dislikeCount} 次点踩
                        </span>
                      </div>
                      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                        <span className="text-xs text-gray-500">{item.course}</span>
                        <div className="flex items-center gap-2">
                          <button className="px-3 py-1 text-xs font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 cursor-pointer whitespace-nowrap">查看完整</button>
                          <button onClick={() => handleReviewAnswer(item.id)} disabled={actionPending} className="px-3 py-1 text-xs font-medium text-red-600 bg-red-50 rounded-md hover:bg-red-100 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">标记错误</button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 举报处理 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">举报处理</h2>
                <div className="space-y-3">
                  {auditReports.map((report) => (
                    <div key={report.id} className="p-4 rounded-lg border border-gray-200 hover:border-gray-300">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="px-2 py-0.5 text-xs font-medium bg-orange-50 text-orange-600 rounded-full">{report.type}</span>
                            <span className="text-xs text-gray-500">{report.time}</span>
                          </div>
                          <div className="text-sm text-gray-900 mb-1">{report.content}</div>
                          <div className="text-xs text-gray-500">举报人: {report.reporter}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
                        <button className="flex-1 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 cursor-pointer whitespace-nowrap">查看详情</button>
                        <button onClick={() => handleResolveReport(report.id, 'delete')} disabled={actionPending} className="flex-1 px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 rounded-md hover:bg-red-100 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">删除内容</button>
                        <button onClick={() => handleResolveReport(report.id, 'reject')} disabled={actionPending} className="flex-1 px-3 py-1.5 text-xs font-medium text-green-600 bg-green-50 rounded-md hover:bg-green-100 cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">驳回举报</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 敏感词配置 */}
            <div className="bg-white rounded-lg p-5 border border-gray-200 mt-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold text-gray-900">敏感词配置</h2>
                <div className="flex items-center gap-2">
                  <input value={newSensitiveWord} onChange={(e) => setNewSensitiveWord(e.target.value)} placeholder="输入敏感词..." className="px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
                  <button onClick={handleAddSensitiveWord} className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap">
                  <i className="ri-add-line mr-1"></i>添加敏感词
                  </button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {sensitiveWords.map((word) => (
                  <div key={word} className="flex items-center gap-2 px-3 py-1.5 bg-red-50 border border-red-100 rounded-lg">
                    <span className="text-sm text-red-600">{word}</span>
                    <button onClick={() => handleRemoveSensitiveWord(word)} className="w-4 h-4 flex items-center justify-center text-red-600 hover:text-red-700 cursor-pointer">
                      <i className="ri-close-line text-xs"></i>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 mb-6">系统设置</h1>
            
            <div className="space-y-5">
              {/* 维护模式 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">维护模式</h2>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 rounded-lg bg-gray-50">
                    <div>
                      <div className="text-sm font-medium text-gray-900">系统维护模式</div>
                      <div className="text-xs text-gray-600 mt-1">开启后将暂停服务并显示维护公告</div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" checked={systemSettings.maintenanceMode} onChange={(e) => setSystemSettings((prev) => ({ ...prev, maintenanceMode: e.target.checked }))} className="sr-only peer" />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-teal-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-600"></div>
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-lg bg-gray-50">
                    <div>
                      <div className="text-sm font-medium text-gray-900">考试周限流</div>
                      <div className="text-xs text-gray-600 mt-1">限制AI调用频次,防止服务器卡顿</div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" checked={systemSettings.examWeekLimit} onChange={(e) => setSystemSettings((prev) => ({ ...prev, examWeekLimit: e.target.checked }))} className="sr-only peer" />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-teal-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-600"></div>
                    </label>
                  </div>
                </div>
              </div>

              {/* 数据备份 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">数据备份</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">自动备份周期</label>
                    <select value={systemSettings.backupSchedule} onChange={(e) => setSystemSettings((prev) => ({ ...prev, backupSchedule: e.target.value }))} className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                      <option>每天 23:00</option>
                      <option>每周日 23:00</option>
                      <option>每月1日 23:00</option>
                    </select>
                  </div>
                  <div className="flex items-center gap-3">
                    <button onClick={handleSaveSystemSettings} disabled={actionPending} className="flex-1 px-4 py-2 text-sm font-medium text-teal-600 border border-teal-600 rounded-lg hover:bg-teal-50 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">立即保存</button>
                    <button className="flex-1 px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap">查看备份历史</button>
                  </div>
                  <div className="p-3 rounded-lg bg-blue-50 border border-blue-100">
                    <div className="flex items-start gap-2">
                      <i className="ri-information-line text-blue-600 text-base mt-0.5"></i>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-blue-900">最近备份</div>
                        <div className="text-xs text-blue-700 mt-1">2024-01-15 23:00 · 数据库 + 知识库 · 大小: 2.3GB</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 全局公告 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">全局公告</h2>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">公告标题</label>
                    <input type="text" value={systemSettings.announcementTitle} onChange={(e) => setSystemSettings((prev) => ({ ...prev, announcementTitle: e.target.value }))} placeholder="输入公告标题..." className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">公告内容</label>
                    <textarea rows={4} value={systemSettings.announcementContent} onChange={(e) => setSystemSettings((prev) => ({ ...prev, announcementContent: e.target.value }))} placeholder="输入公告内容..." className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"></textarea>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">发送范围</label>
                    <select value={systemSettings.announcementAudience} onChange={(e) => setSystemSettings((prev) => ({ ...prev, announcementAudience: e.target.value }))} className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500">
                      <option>全校师生</option>
                      <option>全体教师</option>
                      <option>全体学生</option>
                      <option>指定学院</option>
                    </select>
                  </div>
                  <button onClick={handlePublishAnnouncement} disabled={actionPending} className="w-full px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed">发布公告</button>
                </div>
              </div>

              {/* 基础配置 */}
              <div className="bg-white rounded-lg p-5 border border-gray-200">
                <h2 className="text-base font-semibold text-gray-900 mb-4">基础配置</h2>
                <div className="space-y-3">
                  <div className="flex items-center justify-between py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900">学科专业结构</div>
                      <div className="text-xs text-gray-500 mt-1">维护院系和专业信息</div>
                    </div>
                    <button className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap">管理</button>
                  </div>
                  <div className="flex items-center justify-between py-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900">统一认证配置</div>
                      <div className="text-xs text-gray-500 mt-1">对接校园CAS认证系统</div>
                    </div>
                    <button className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap">配置</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      <ProductSidePanel role="admin" />
    </div>
  );
}
