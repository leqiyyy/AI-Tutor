import { useEffect, useState, type ChangeEvent } from 'react';
import { settingsService } from '@/services/settings';
import type {
  DeviceSession,
  TeacherAchievement,
  TeacherAiSettings,
  TeacherNotificationSettings,
  TeacherProfileSettings,
} from '@/types/settings';

type ProfileForm = TeacherProfileSettings;
type PasswordForm = {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
};
type NotificationSettings = TeacherNotificationSettings;
type AISettings = TeacherAiSettings;

const SECTION_TABS = [
  { id: 'profile', label: '基本信息', icon: 'ri-user-line' },
  { id: 'school', label: '学校背景', icon: 'ri-building-line' },
  { id: 'academic', label: '学术信息', icon: 'ri-graduation-cap-line' },
  { id: 'security', label: '安全设置', icon: 'ri-shield-line' },
  { id: 'notification', label: '通知偏好', icon: 'ri-notification-line' },
  { id: 'ai', label: 'AI助教配置', icon: 'ri-robot-line' },
];

const EMPTY_PROFILE_FORM: ProfileForm = {
  name: '',
  nameEn: '',
  gender: 'male',
  birthday: '',
  bio: '',
  email: '',
  phone: '',
  wechat: '',
  website: '',
  school: '',
  college: '',
  department: '',
  title: '',
  employeeId: '',
  teacherType: 'full',
  researchArea: '',
  officeLocation: '',
  officeHours: '',
  education: '',
  graduateSchool: '',
  degree: '',
  graduateYear: '',
  joinYear: '',
  teachingYears: '',
};

const EMPTY_PASSWORD_FORM: PasswordForm = {
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
};

const EMPTY_NOTIFICATION_SETTINGS: NotificationSettings = {
  siteNotify: false,
  emailNotify: false,
  wechatNotify: false,
  studentQuestion: false,
  aiDislike: false,
  deadlineRemind: false,
  systemUpdate: false,
};

const EMPTY_AI_SETTINGS: AISettings = {
  defaultStyle: 'academic',
  autoReply: false,
  knowledgeBase: false,
  responseLanguage: 'zh',
  maxTokens: '1000',
};

function getDeviceMeta(deviceName: string) {
  const [browser, platform] = deviceName.split(' on ');
  const lower = deviceName.toLowerCase();

  if (lower.includes('iphone')) {
    return { title: 'iPhone', browser: browser || deviceName, icon: 'ri-smartphone-line' };
  }
  if (lower.includes('ipad')) {
    return { title: 'iPad', browser: browser || deviceName, icon: 'ri-tablet-line' };
  }
  if (lower.includes('mac')) {
    return { title: platform || 'Mac', browser: browser || deviceName, icon: 'ri-macbook-line' };
  }

  return {
    title: platform || deviceName,
    browser: browser || deviceName,
    icon: 'ri-computer-line',
  };
}

export default function TeacherSettings() {
  const [activeSection, setActiveSection] = useState('profile');
  const [avatarPreview, setAvatarPreview] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showDevicesModal, setShowDevicesModal] = useState(false);
  const [show2FAModal, setShow2FAModal] = useState(false);
  const [twoFAEnabled, setTwoFAEnabled] = useState(false);
  const [devices, setDevices] = useState<DeviceSession[]>([]);

  const [profileForm, setProfileForm] = useState<ProfileForm>(EMPTY_PROFILE_FORM);
  const [passwordForm, setPasswordForm] = useState<PasswordForm>(EMPTY_PASSWORD_FORM);
  const [notificationSettings, setNotificationSettings] = useState<NotificationSettings>(EMPTY_NOTIFICATION_SETTINGS);
  const [aiSettings, setAISettings] = useState<AISettings>(EMPTY_AI_SETTINGS);
  const [achievements, setAchievements] = useState<TeacherAchievement[]>([]);

  const [newAchievement, setNewAchievement] = useState({ type: 'paper', title: '', year: '', journal: '' });
  const [showAddAchievement, setShowAddAchievement] = useState(false);

  useEffect(() => {
    let mounted = true;

    const loadSettings = async () => {
      try {
        setErrorMessage('');
        const [settings, deviceSessions] = await Promise.all([
          settingsService.getTeacherSettings(),
          settingsService.getDevices(),
        ]);

        if (!mounted) {
          return;
        }

        setProfileForm(settings.profile);
        setNotificationSettings(settings.notifications);
        setAISettings(settings.ai);
        setAchievements(settings.achievements);
        setAvatarPreview(settings.avatarUrl ?? '');
        setDevices(deviceSessions);
      } catch (error) {
        if (mounted) {
          setErrorMessage(error instanceof Error ? error.message : '教师设置加载失败，请稍后重试');
        }
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    };

    loadSettings();

    return () => {
      mounted = false;
    };
  }, []);

  const showSaveSuccess = () => {
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  const handleAvatarUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      setErrorMessage('');
      const result = await settingsService.uploadAvatar({ fileName: file.name });
      setAvatarPreview(result.url);
      showSaveSuccess();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '头像上传失败，请稍后重试');
    } finally {
      e.target.value = '';
    }
  };

  const handleSave = async () => {
    try {
      setErrorMessage('');
      setIsSaving(true);

      const updated = await settingsService.updateTeacherSettings({
        profile: profileForm,
        notifications: notificationSettings,
        ai: aiSettings,
        achievements,
        avatarUrl: avatarPreview || undefined,
      });

      setProfileForm(updated.profile);
      setNotificationSettings(updated.notifications);
      setAISettings(updated.ai);
      setAchievements(updated.achievements);
      setAvatarPreview(updated.avatarUrl ?? avatarPreview);
      showSaveSuccess();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : '保存失败，请稍后重试');
    } finally {
      setIsSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (!passwordForm.oldPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
      setPasswordError('请填写完整的密码信息');
      return;
    }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError('两次输入的密码不一致');
      return;
    }

    try {
      setPasswordError('');
      setErrorMessage('');
      await settingsService.changePassword(passwordForm);
      setShowPasswordModal(false);
      setPasswordForm(EMPTY_PASSWORD_FORM);
      showSaveSuccess();
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : '密码修改失败，请稍后重试');
    }
  };

  const handleAddAchievement = () => {
    if (!newAchievement.title) return;
    setAchievements(prev => [...prev, { ...newAchievement, id: Date.now() }]);
    setNewAchievement({ type: 'paper', title: '', year: '', journal: '' });
    setShowAddAchievement(false);
  };

  const handleRemoveAchievement = (id: number) => {
    setAchievements(prev => prev.filter(a => a.id !== id));
  };

  const inputClass = 'w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white transition-colors';
  const labelClass = 'block text-sm font-medium text-gray-700 mb-1.5';

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="rounded-xl border border-gray-200 bg-white px-6 py-10 text-center text-sm text-gray-500">
          正在加载教师设置...
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* 页面标题 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">个人设置</h1>
        <p className="text-sm text-gray-500 mt-1">管理您的个人信息、学校背景和系统偏好</p>
      </div>

      {/* 保存成功提示 */}
      {saveSuccess && (
        <div className="mb-4 px-4 py-3 bg-teal-50 border border-teal-200 rounded-lg flex items-center gap-2 text-teal-700 text-sm">
          <i className="ri-checkbox-circle-line text-base"></i>
          <span>保存成功！您的信息已更新。</span>
        </div>
      )}

      {errorMessage && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
          <i className="ri-error-warning-line text-base"></i>
          <span>{errorMessage}</span>
        </div>
      )}

      <div className="flex gap-6">
        {/* 左侧导航 */}
        <div className="w-52 flex-shrink-0">
          {/* 头像卡片 */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4 text-center">
            <div className="relative inline-block mb-3">
              {avatarPreview ? (
                <img src={avatarPreview} alt="头像" className="w-20 h-20 rounded-full object-cover mx-auto" />
              ) : (
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-teal-400 to-teal-600 flex items-center justify-center text-white text-2xl font-bold mx-auto">
                  王
                </div>
              )}
              <label
                htmlFor="avatar-upload"
                className="absolute bottom-0 right-0 w-6 h-6 bg-teal-500 rounded-full flex items-center justify-center cursor-pointer hover:bg-teal-600 transition-colors"
              >
                <i className="ri-camera-line text-white text-xs"></i>
              </label>
              <input type="file" id="avatar-upload" accept="image/*" onChange={handleAvatarUpload} className="hidden" />
            </div>
            <div className="text-sm font-semibold text-gray-900">{profileForm.name}</div>
            <div className="text-xs text-gray-500 mt-0.5">{profileForm.title} · {profileForm.college}</div>
            <div className="mt-2 px-2 py-1 bg-teal-50 rounded-full text-xs text-teal-600 font-medium">
              工号 {profileForm.employeeId.split('-').pop()}
            </div>
          </div>

          {/* 导航菜单 */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {SECTION_TABS.map((tab, idx) => (
              <button
                key={tab.id}
                onClick={() => setActiveSection(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors cursor-pointer whitespace-nowrap text-left ${
                  idx !== 0 ? 'border-t border-gray-100' : ''
                } ${
                  activeSection === tab.id
                    ? 'bg-teal-50 text-teal-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
              >
                <div className="w-5 h-5 flex items-center justify-center">
                  <i className={`${tab.icon} text-base`}></i>
                </div>
                {tab.label}
                {activeSection === tab.id && (
                  <i className="ri-arrow-right-s-line ml-auto text-teal-500"></i>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* 右侧内容 */}
        <div className="flex-1 min-w-0 space-y-5">

          {/* ===== 基本信息 ===== */}
          {activeSection === 'profile' && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-teal-50">
                    <i className="ri-user-line text-teal-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">基本信息</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>姓名（中文）</label>
                    <input type="text" value={profileForm.name} onChange={e => setProfileForm({ ...profileForm, name: e.target.value })} className={inputClass} />
                  </div>
                  <div>
                    <label className={labelClass}>姓名（英文）</label>
                    <input type="text" value={profileForm.nameEn} onChange={e => setProfileForm({ ...profileForm, nameEn: e.target.value })} className={inputClass} placeholder="Pinyin or English name" />
                  </div>
                  <div>
                    <label className={labelClass}>性别</label>
                    <select value={profileForm.gender} onChange={e => setProfileForm({ ...profileForm, gender: e.target.value })} className={inputClass + ' cursor-pointer'}>
                      <option value="male">男</option>
                      <option value="female">女</option>
                      <option value="other">不便透露</option>
                    </select>
                  </div>
                  <div>
                    <label className={labelClass}>出生日期</label>
                    <input type="date" value={profileForm.birthday} onChange={e => setProfileForm({ ...profileForm, birthday: e.target.value })} className={inputClass} />
                  </div>
                </div>

                <div className="mt-4">
                  <label className={labelClass}>个人简介</label>
                  <textarea
                    rows={4}
                    value={profileForm.bio}
                    onChange={e => setProfileForm({ ...profileForm, bio: e.target.value })}
                    placeholder="介绍您的教学经历、研究方向和学术成就..."
                    className={inputClass + ' resize-none'}
                    maxLength={500}
                  />
                  <div className="text-xs text-gray-400 text-right mt-1">{profileForm.bio.length}/500</div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-blue-50">
                    <i className="ri-contacts-line text-blue-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">联系方式</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>
                      <i className="ri-mail-line mr-1 text-gray-400"></i>邮箱地址
                    </label>
                    <input type="email" value={profileForm.email} onChange={e => setProfileForm({ ...profileForm, email: e.target.value })} className={inputClass} />
                  </div>
                  <div>
                    <label className={labelClass}>
                      <i className="ri-phone-line mr-1 text-gray-400"></i>手机号码
                    </label>
                    <input type="tel" value={profileForm.phone} onChange={e => setProfileForm({ ...profileForm, phone: e.target.value })} className={inputClass} placeholder="请输入手机号码" />
                  </div>
                  <div>
                    <label className={labelClass}>
                      <i className="ri-wechat-line mr-1 text-gray-400"></i>微信号
                    </label>
                    <input type="text" value={profileForm.wechat} onChange={e => setProfileForm({ ...profileForm, wechat: e.target.value })} className={inputClass} placeholder="请输入微信号" />
                  </div>
                  <div>
                    <label className={labelClass}>
                      <i className="ri-global-line mr-1 text-gray-400"></i>个人主页
                    </label>
                    <input type="url" value={profileForm.website} onChange={e => setProfileForm({ ...profileForm, website: e.target.value })} className={inputClass} placeholder="https://" />
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={() => setProfileForm(prev => ({ ...prev }))} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap">重置</button>
                <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed">保存修改</button>
              </div>
            </>
          )}

          {/* ===== 学校背景 ===== */}
          {activeSection === 'school' && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-orange-50">
                    <i className="ri-building-line text-orange-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">所在单位</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>所在学校</label>
                    <input type="text" value={profileForm.school} onChange={e => setProfileForm({ ...profileForm, school: e.target.value })} className={inputClass} placeholder="请输入学校全称" />
                  </div>
                  <div>
                    <label className={labelClass}>所在学院</label>
                    <input type="text" value={profileForm.college} onChange={e => setProfileForm({ ...profileForm, college: e.target.value })} className={inputClass} placeholder="请输入学院名称" />
                  </div>
                  <div>
                    <label className={labelClass}>所在系/部门</label>
                    <input type="text" value={profileForm.department} onChange={e => setProfileForm({ ...profileForm, department: e.target.value })} className={inputClass} placeholder="请输入系或部门名称" />
                  </div>
                  <div>
                    <label className={labelClass}>职称</label>
                    <select value={profileForm.title} onChange={e => setProfileForm({ ...profileForm, title: e.target.value })} className={inputClass + ' cursor-pointer'}>
                      <option value="">请选择职称</option>
                      <option value="助教">助教</option>
                      <option value="讲师">讲师</option>
                      <option value="副教授">副教授</option>
                      <option value="教授">教授</option>
                      <option value="研究员">研究员</option>
                      <option value="副研究员">副研究员</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-teal-50">
                    <i className="ri-id-card-line text-teal-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">工号与任职信息</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>工号</label>
                    <div className="relative">
                      <input type="text" value={profileForm.employeeId} onChange={e => setProfileForm({ ...profileForm, employeeId: e.target.value })} className={inputClass + ' pr-10'} placeholder="请输入工号" />
                      <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center">
                        <i className="ri-lock-line text-gray-400 text-sm"></i>
                      </div>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">工号由学校统一分配，如需修改请联系管理员</p>
                  </div>
                  <div>
                    <label className={labelClass}>教师类型</label>
                    <select value={profileForm.teacherType} onChange={e => setProfileForm({ ...profileForm, teacherType: e.target.value })} className={inputClass + ' cursor-pointer'}>
                      <option value="full">专任教师</option>
                      <option value="part">兼职教师</option>
                      <option value="visiting">访问学者</option>
                      <option value="postdoc">博士后</option>
                      <option value="admin">行政兼课</option>
                    </select>
                  </div>
                  <div>
                    <label className={labelClass}>入职年份</label>
                    <input type="number" value={profileForm.joinYear} onChange={e => setProfileForm({ ...profileForm, joinYear: e.target.value })} className={inputClass} placeholder="例如：2005" min="1950" max="2030" />
                  </div>
                  <div>
                    <label className={labelClass}>教龄（年）</label>
                    <input type="number" value={profileForm.teachingYears} onChange={e => setProfileForm({ ...profileForm, teachingYears: e.target.value })} className={inputClass} placeholder="请输入教龄" min="0" max="60" />
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-green-50">
                    <i className="ri-map-pin-line text-green-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">办公信息</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>办公室地址</label>
                    <input type="text" value={profileForm.officeLocation} onChange={e => setProfileForm({ ...profileForm, officeLocation: e.target.value })} className={inputClass} placeholder="例如：计算机楼 A512" />
                  </div>
                  <div>
                    <label className={labelClass}>办公时间</label>
                    <input type="text" value={profileForm.officeHours} onChange={e => setProfileForm({ ...profileForm, officeHours: e.target.value })} className={inputClass} placeholder="例如：周二、周四 14:00-16:00" />
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed">保存修改</button>
              </div>
            </>
          )}

          {/* ===== 学术信息 ===== */}
          {activeSection === 'academic' && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-purple-50">
                    <i className="ri-graduation-cap-line text-purple-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">教育背景</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>最高学历</label>
                    <select value={profileForm.education} onChange={e => setProfileForm({ ...profileForm, education: e.target.value })} className={inputClass + ' cursor-pointer'}>
                      <option value="本科">本科</option>
                      <option value="硕士">硕士</option>
                      <option value="博士">博士</option>
                      <option value="博士后">博士后</option>
                    </select>
                  </div>
                  <div>
                    <label className={labelClass}>毕业院校</label>
                    <input type="text" value={profileForm.graduateSchool} onChange={e => setProfileForm({ ...profileForm, graduateSchool: e.target.value })} className={inputClass} placeholder="请输入毕业院校" />
                  </div>
                  <div>
                    <label className={labelClass}>学位名称</label>
                    <input type="text" value={profileForm.degree} onChange={e => setProfileForm({ ...profileForm, degree: e.target.value })} className={inputClass} placeholder="例如：工学博士" />
                  </div>
                  <div>
                    <label className={labelClass}>毕业年份</label>
                    <input type="number" value={profileForm.graduateYear} onChange={e => setProfileForm({ ...profileForm, graduateYear: e.target.value })} className={inputClass} placeholder="例如：2005" min="1950" max="2030" />
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-blue-50">
                    <i className="ri-microscope-line text-blue-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">研究方向</h2>
                </div>

                <div>
                  <label className={labelClass}>主要研究领域</label>
                  <textarea
                    rows={3}
                    value={profileForm.researchArea}
                    onChange={e => setProfileForm({ ...profileForm, researchArea: e.target.value })}
                    placeholder="请输入您的研究方向，多个方向用逗号分隔..."
                    className={inputClass + ' resize-none'}
                  />
                  <p className="text-xs text-gray-400 mt-1">多个研究方向请用逗号分隔，将展示在您的公开主页上</p>
                </div>

                {/* 研究方向标签预览 */}
                <div className="mt-3 flex flex-wrap gap-2">
                  {profileForm.researchArea.split('、').concat(profileForm.researchArea.split(',')).filter((v, i, a) => v.trim() && a.indexOf(v) === i).map((area, idx) => (
                    <span key={idx} className="px-3 py-1 bg-blue-50 text-blue-700 text-xs rounded-full font-medium">
                      {area.trim()}
                    </span>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-orange-50">
                      <i className="ri-trophy-line text-orange-600 text-sm"></i>
                    </div>
                    <h2 className="text-base font-semibold text-gray-900">学术成果</h2>
                  </div>
                  <button
                    onClick={() => setShowAddAchievement(true)}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-teal-600 bg-teal-50 rounded-lg hover:bg-teal-100 transition-colors cursor-pointer whitespace-nowrap"
                  >
                    <i className="ri-add-line"></i>添加
                  </button>
                </div>

                <div className="space-y-3">
                  {achievements.map(item => (
                    <div key={item.id} className="flex items-start gap-3 p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors group">
                      <div className={`w-8 h-8 flex items-center justify-center rounded-lg flex-shrink-0 ${
                        item.type === 'paper' ? 'bg-blue-50' :
                        item.type === 'award' ? 'bg-yellow-50' : 'bg-green-50'
                      }`}>
                        <i className={`text-sm ${
                          item.type === 'paper' ? 'ri-article-line text-blue-600' :
                          item.type === 'award' ? 'ri-award-line text-yellow-600' : 'ri-funds-line text-green-600'
                        }`}></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 leading-snug">{item.title}</div>
                        <div className="text-xs text-gray-500 mt-1">{item.journal} · {item.year}</div>
                      </div>
                      <button
                        onClick={() => handleRemoveAchievement(item.id)}
                        className="opacity-0 group-hover:opacity-100 w-6 h-6 flex items-center justify-center text-gray-400 hover:text-red-500 transition-all cursor-pointer"
                      >
                        <i className="ri-delete-bin-line text-sm"></i>
                      </button>
                    </div>
                  ))}
                </div>

                {showAddAchievement && (
                  <div className="mt-4 p-4 border border-teal-200 rounded-lg bg-teal-50/30">
                    <div className="grid grid-cols-2 gap-3 mb-3">
                      <div>
                        <label className={labelClass}>类型</label>
                        <select value={newAchievement.type} onChange={e => setNewAchievement({ ...newAchievement, type: e.target.value })} className={inputClass + ' cursor-pointer'}>
                          <option value="paper">论文</option>
                          <option value="award">奖项</option>
                          <option value="project">项目</option>
                        </select>
                      </div>
                      <div>
                        <label className={labelClass}>年份</label>
                        <input type="number" value={newAchievement.year} onChange={e => setNewAchievement({ ...newAchievement, year: e.target.value })} className={inputClass} placeholder="例如：2024" />
                      </div>
                      <div className="col-span-2">
                        <label className={labelClass}>标题</label>
                        <input type="text" value={newAchievement.title} onChange={e => setNewAchievement({ ...newAchievement, title: e.target.value })} className={inputClass} placeholder="请输入成果标题" />
                      </div>
                      <div className="col-span-2">
                        <label className={labelClass}>期刊/机构</label>
                        <input type="text" value={newAchievement.journal} onChange={e => setNewAchievement({ ...newAchievement, journal: e.target.value })} className={inputClass} placeholder="请输入期刊或颁奖机构" />
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={handleAddAchievement} className="px-4 py-1.5 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap">确认添加</button>
                      <button onClick={() => setShowAddAchievement(false)} className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap">取消</button>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed">保存修改</button>
              </div>
            </>
          )}

          {/* ===== 安全设置 ===== */}
          {activeSection === 'security' && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-red-50">
                    <i className="ri-shield-keyhole-line text-red-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">账号安全</h2>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 flex items-center justify-center rounded-lg bg-gray-100">
                        <i className="ri-lock-password-line text-gray-600 text-base"></i>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900">登录密码</div>
                        <div className="text-xs text-gray-500 mt-0.5">上次修改：30天前 · 建议定期更换密码</div>
                      </div>
                    </div>
                    <button onClick={() => setShowPasswordModal(true)} className="px-4 py-2 text-sm font-medium text-teal-600 border border-teal-200 rounded-lg hover:bg-teal-50 transition-colors cursor-pointer whitespace-nowrap">
                      修改密码
                    </button>
                  </div>

                  <div className="flex items-center justify-between p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 flex items-center justify-center rounded-lg bg-gray-100">
                        <i className="ri-shield-check-line text-gray-600 text-base"></i>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900">两步验证</div>
                        <div className="text-xs text-gray-500 mt-0.5">
                          {twoFAEnabled ? '已开启 · 登录时需要验证码' : '未开启 · 开启后可大幅提升账号安全性'}
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => setShow2FAModal(true)}
                      className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
                        twoFAEnabled
                          ? 'text-red-600 border border-red-200 hover:bg-red-50'
                          : 'text-teal-600 border border-teal-200 hover:bg-teal-50'
                      }`}
                    >
                      {twoFAEnabled ? '关闭' : '开启'}
                    </button>
                  </div>

                  <div className="flex items-center justify-between p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 flex items-center justify-center rounded-lg bg-gray-100">
                        <i className="ri-mail-check-line text-gray-600 text-base"></i>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900">绑定邮箱</div>
                        <div className="text-xs text-gray-500 mt-0.5">已绑定：{profileForm.email}</div>
                      </div>
                    </div>
                    <button className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap">
                      更换邮箱
                    </button>
                  </div>

                  <div className="flex items-center justify-between p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 flex items-center justify-center rounded-lg bg-gray-100">
                        <i className="ri-smartphone-line text-gray-600 text-base"></i>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900">绑定手机</div>
                        <div className="text-xs text-gray-500 mt-0.5">已绑定：{profileForm.phone || '未绑定'}</div>
                      </div>
                    </div>
                    <button className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer whitespace-nowrap">
                      {profileForm.phone ? '更换手机' : '立即绑定'}
                    </button>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-blue-50">
                      <i className="ri-computer-line text-blue-600 text-sm"></i>
                    </div>
                    <h2 className="text-base font-semibold text-gray-900">登录设备管理</h2>
                  </div>
                  <button onClick={() => setShowDevicesModal(true)} className="text-sm text-teal-600 hover:text-teal-700 cursor-pointer whitespace-nowrap">查看全部</button>
                </div>

                <div className="space-y-3">
                  {devices.slice(0, 3).map((device) => {
                    const meta = getDeviceMeta(device.deviceName);

                    return (
                    <div key={device.id} className="flex items-center gap-3 p-3 border border-gray-100 rounded-lg">
                      <div className="w-9 h-9 flex items-center justify-center rounded-lg bg-gray-100 flex-shrink-0">
                        <i className={`${meta.icon} text-gray-600 text-base`}></i>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-900">{meta.title}</span>
                          {device.current && <span className="px-2 py-0.5 text-xs bg-teal-50 text-teal-600 rounded-full font-medium">当前</span>}
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5">{meta.browser} · {device.location} · {device.lastActiveAt}</div>
                      </div>
                      {!device.current && (
                        <button className="text-xs text-red-500 hover:text-red-600 cursor-pointer whitespace-nowrap">移除</button>
                      )}
                    </div>
                    );
                  })}
                </div>
              </div>

              <div className="bg-white rounded-xl border border-red-100 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-red-50">
                    <i className="ri-error-warning-line text-red-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">危险操作</h2>
                </div>
                <div className="flex items-center justify-between p-4 border border-red-100 rounded-lg bg-red-50/30">
                  <div>
                    <div className="text-sm font-medium text-gray-900">注销账号</div>
                    <div className="text-xs text-gray-500 mt-0.5">注销后所有数据将被永久删除，此操作不可撤销</div>
                  </div>
                  <button className="px-4 py-2 text-sm font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors cursor-pointer whitespace-nowrap">
                    申请注销
                  </button>
                </div>
              </div>
            </>
          )}

          {/* ===== 通知偏好 ===== */}
          {activeSection === 'notification' && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-teal-50">
                    <i className="ri-notification-line text-teal-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">通知渠道</h2>
                </div>

                <div className="space-y-4">
                  {[
                    { key: 'siteNotify', label: '站内通知', desc: '在平台内接收实时通知消息', icon: 'ri-notification-3-line' },
                    { key: 'emailNotify', label: '邮件提醒', desc: `发送到 ${profileForm.email}`, icon: 'ri-mail-line' },
                    { key: 'wechatNotify', label: '微信推送', desc: '通过微信公众号接收通知（需先绑定微信）', icon: 'ri-wechat-line' },
                  ].map(item => (
                    <div key={item.key} className="flex items-center justify-between p-4 border border-gray-100 rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 flex items-center justify-center rounded-lg bg-gray-100">
                          <i className={`${item.icon} text-gray-600 text-base`}></i>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-gray-900">{item.label}</div>
                          <div className="text-xs text-gray-500 mt-0.5">{item.desc}</div>
                        </div>
                      </div>
                      <button
                        onClick={() => setNotificationSettings(prev => ({ ...prev, [item.key]: !prev[item.key as keyof NotificationSettings] }))}
                        className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer flex-shrink-0 ${
                          notificationSettings[item.key as keyof NotificationSettings] ? 'bg-teal-500' : 'bg-gray-200'
                        }`}
                      >
                        <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                          notificationSettings[item.key as keyof NotificationSettings] ? 'translate-x-5' : 'translate-x-0'
                        }`}></span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-orange-50">
                    <i className="ri-filter-line text-orange-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">通知类型</h2>
                </div>

                <div className="space-y-3">
                  {[
                    { key: 'studentQuestion', label: '学生提问', desc: '学生在课程中提出新问题时通知', icon: 'ri-question-line', color: 'blue' },
                    { key: 'aiDislike', label: 'AI回答被点踩', desc: 'AI助教回答被学生标记为不满意时通知', icon: 'ri-thumb-down-line', color: 'red' },
                    { key: 'deadlineRemind', label: '作业截止提醒', desc: '作业截止前3小时发送提醒', icon: 'ri-time-line', color: 'orange' },
                    { key: 'systemUpdate', label: '系统更新公告', desc: '平台功能更新和维护通知', icon: 'ri-settings-line', color: 'gray' },
                  ].map(item => (
                    <div key={item.key} className="flex items-center justify-between p-3 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 flex items-center justify-center rounded-lg ${
                          item.color === 'blue' ? 'bg-blue-50' :
                          item.color === 'red' ? 'bg-red-50' :
                          item.color === 'orange' ? 'bg-orange-50' : 'bg-gray-100'
                        }`}>
                          <i className={`${item.icon} text-sm ${
                            item.color === 'blue' ? 'text-blue-600' :
                            item.color === 'red' ? 'text-red-600' :
                            item.color === 'orange' ? 'text-orange-600' : 'text-gray-600'
                          }`}></i>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-gray-900">{item.label}</div>
                          <div className="text-xs text-gray-500">{item.desc}</div>
                        </div>
                      </div>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={notificationSettings[item.key as keyof NotificationSettings] as boolean}
                          onChange={() => setNotificationSettings(prev => ({ ...prev, [item.key]: !prev[item.key as keyof NotificationSettings] }))}
                          className="w-4 h-4 text-teal-600 border-gray-300 rounded focus:ring-teal-500 cursor-pointer"
                        />
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed">保存设置</button>
              </div>
            </>
          )}

          {/* ===== AI助教配置 ===== */}
          {activeSection === 'ai' && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-teal-50">
                    <i className="ri-robot-line text-teal-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">AI助教基础配置</h2>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className={labelClass}>默认回答风格</label>
                    <div className="grid grid-cols-3 gap-3">
                      {[
                        { value: 'academic', label: '严谨学术型', desc: '引用文献，逻辑严密', icon: 'ri-book-2-line' },
                        { value: 'guide', label: '启发引导型', desc: '循序渐进，引导思考', icon: 'ri-lightbulb-line' },
                        { value: 'debug', label: 'Debug调试型', desc: '聚焦代码，逐步排查', icon: 'ri-bug-line' },
                      ].map(style => (
                        <button
                          key={style.value}
                          onClick={() => setAISettings(prev => ({ ...prev, defaultStyle: style.value }))}
                          className={`p-4 border-2 rounded-xl text-left transition-all cursor-pointer ${
                            aiSettings.defaultStyle === style.value
                              ? 'border-teal-500 bg-teal-50'
                              : 'border-gray-200 hover:border-gray-300'
                          }`}
                        >
                          <div className={`w-8 h-8 flex items-center justify-center rounded-lg mb-2 ${
                            aiSettings.defaultStyle === style.value ? 'bg-teal-100' : 'bg-gray-100'
                          }`}>
                            <i className={`${style.icon} text-base ${aiSettings.defaultStyle === style.value ? 'text-teal-600' : 'text-gray-600'}`}></i>
                          </div>
                          <div className={`text-sm font-medium ${aiSettings.defaultStyle === style.value ? 'text-teal-700' : 'text-gray-900'}`}>{style.label}</div>
                          <div className="text-xs text-gray-500 mt-0.5">{style.desc}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className={labelClass}>回答语言</label>
                      <select value={aiSettings.responseLanguage} onChange={e => setAISettings(prev => ({ ...prev, responseLanguage: e.target.value }))} className={inputClass + ' cursor-pointer'}>
                        <option value="zh">中文</option>
                        <option value="en">English</option>
                        <option value="auto">自动识别</option>
                      </select>
                    </div>
                    <div>
                      <label className={labelClass}>最大回答长度</label>
                      <select value={aiSettings.maxTokens} onChange={e => setAISettings(prev => ({ ...prev, maxTokens: e.target.value }))} className={inputClass + ' cursor-pointer'}>
                        <option value="500">简短（约500字）</option>
                        <option value="1000">适中（约1000字）</option>
                        <option value="2000">详细（约2000字）</option>
                        <option value="4000">完整（约4000字）</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-green-50">
                    <i className="ri-settings-3-line text-green-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">功能开关</h2>
                </div>

                <div className="space-y-4">
                  {[
                    { key: 'autoReply', label: '自动回复学生提问', desc: '学生提问后AI立即自动回复，无需等待教师审核' },
                    { key: 'knowledgeBase', label: '启用课程知识库', desc: '基于上传的课程资料进行精准回答' },
                  ].map(item => (
                    <div key={item.key} className="flex items-center justify-between p-4 border border-gray-100 rounded-lg">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{item.label}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{item.desc}</div>
                      </div>
                      <button
                        onClick={() => setAISettings(prev => ({ ...prev, [item.key]: !prev[item.key as keyof AISettings] }))}
                        className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer flex-shrink-0 ${
                          aiSettings[item.key as keyof AISettings] ? 'bg-teal-500' : 'bg-gray-200'
                        }`}
                      >
                        <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                          aiSettings[item.key as keyof AISettings] ? 'translate-x-5' : 'translate-x-0'
                        }`}></span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-blue-50">
                    <i className="ri-bar-chart-line text-blue-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">AI使用统计</h2>
                </div>
                <div className="grid grid-cols-4 gap-4">
                  {[
                    { label: '本月对话次数', value: '1,284', icon: 'ri-chat-3-line', color: 'teal' },
                    { label: '平均满意度', value: '4.7', icon: 'ri-star-line', color: 'yellow' },
                    { label: '知识库文件', value: '38', icon: 'ri-file-list-line', color: 'blue' },
                    { label: '分担提问率', value: '78%', icon: 'ri-pie-chart-line', color: 'green' },
                  ].map((stat, idx) => (
                    <div key={idx} className="p-4 bg-gray-50 rounded-xl text-center">
                      <div className={`w-9 h-9 flex items-center justify-center rounded-lg mx-auto mb-2 ${
                        stat.color === 'teal' ? 'bg-teal-100' :
                        stat.color === 'yellow' ? 'bg-yellow-100' :
                        stat.color === 'blue' ? 'bg-blue-100' : 'bg-green-100'
                      }`}>
                        <i className={`${stat.icon} text-base ${
                          stat.color === 'teal' ? 'text-teal-600' :
                          stat.color === 'yellow' ? 'text-yellow-600' :
                          stat.color === 'blue' ? 'text-blue-600' : 'text-green-600'
                        }`}></i>
                      </div>
                      <div className="text-lg font-bold text-gray-900">{stat.value}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{stat.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed">保存配置</button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* 修改密码弹窗 */}
      {showPasswordModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900">修改密码</h2>
              <button onClick={() => setShowPasswordModal(false)} className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer">
                <i className="ri-close-line text-lg"></i>
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              {[
                { key: 'oldPassword', label: '当前密码', placeholder: '请输入当前密码' },
                { key: 'newPassword', label: '新密码', placeholder: '请输入新密码（至少8位）' },
                { key: 'confirmPassword', label: '确认新密码', placeholder: '请再次输入新密码' },
              ].map(field => (
                <div key={field.key}>
                  <label className={labelClass}>{field.label}</label>
                  <input
                    type="password"
                    value={passwordForm[field.key as keyof PasswordForm]}
                    onChange={e => setPasswordForm(prev => ({ ...prev, [field.key]: e.target.value }))}
                    placeholder={field.placeholder}
                    className={inputClass}
                  />
                </div>
              ))}
              {passwordForm.newPassword && passwordForm.confirmPassword && passwordForm.newPassword !== passwordForm.confirmPassword && (
                <p className="text-xs text-red-500">两次输入的密码不一致</p>
              )}
              {passwordError && <p className="text-xs text-red-500">{passwordError}</p>}
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button onClick={() => { setShowPasswordModal(false); setPasswordError(''); }} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap">取消</button>
              <button onClick={handleChangePassword} className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap">确认修改</button>
            </div>
          </div>
        </div>
      )}

      {/* 两步验证弹窗 */}
      {show2FAModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900">{twoFAEnabled ? '关闭两步验证' : '开启两步验证'}</h2>
              <button onClick={() => setShow2FAModal(false)} className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer">
                <i className="ri-close-line text-lg"></i>
              </button>
            </div>
            <div className="px-6 py-5">
              {!twoFAEnabled ? (
                <div className="text-center">
                  <div className="w-16 h-16 bg-teal-50 rounded-full flex items-center justify-center mx-auto mb-4">
                    <i className="ri-shield-check-line text-teal-600 text-3xl"></i>
                  </div>
                  <p className="text-sm text-gray-600 mb-4">开启两步验证后，每次登录时除密码外还需输入手机验证码，大幅提升账号安全性。</p>
                  <div className="p-3 bg-gray-50 rounded-lg text-left mb-4">
                    <div className="text-xs text-gray-500 mb-1">验证码将发送至</div>
                    <div className="text-sm font-medium text-gray-900">{profileForm.phone || '未绑定手机，请先绑定'}</div>
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
                    <i className="ri-shield-cross-line text-red-500 text-3xl"></i>
                  </div>
                  <p className="text-sm text-gray-600">关闭两步验证后，账号安全性将降低。确认要关闭吗？</p>
                </div>
              )}
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button onClick={() => setShow2FAModal(false)} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 cursor-pointer whitespace-nowrap">取消</button>
              <button
                onClick={() => { setTwoFAEnabled(!twoFAEnabled); setShow2FAModal(false); }}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors cursor-pointer whitespace-nowrap ${
                  twoFAEnabled ? 'bg-red-500 text-white hover:bg-red-600' : 'bg-teal-600 text-white hover:bg-teal-700'
                }`}
              >
                {twoFAEnabled ? '确认关闭' : '确认开启'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 设备管理弹窗 */}
      {showDevicesModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-lg">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-900">登录设备管理</h2>
              <button onClick={() => setShowDevicesModal(false)} className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer">
                <i className="ri-close-line text-lg"></i>
              </button>
            </div>
            <div className="px-6 py-5 space-y-3">
              {devices.map((device) => {
                const meta = getDeviceMeta(device.deviceName);

                return (
                <div key={device.id} className="flex items-start gap-3 p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                  <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 flex-shrink-0">
                    <i className={`${meta.icon} text-gray-600 text-lg`}></i>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-gray-900">{meta.title}</span>
                      {device.current && <span className="px-2 py-0.5 text-xs bg-teal-50 text-teal-600 rounded-full font-medium">当前设备</span>}
                    </div>
                    <div className="text-xs text-gray-500 space-y-0.5">
                      <div>{meta.browser}</div>
                      <div>{device.location}</div>
                      <div>{device.lastActiveAt}</div>
                    </div>
                  </div>
                  {!device.current && (
                    <button className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors cursor-pointer whitespace-nowrap">
                      移除
                    </button>
                  )}
                </div>
                );
              })}
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
              <button className="text-sm text-red-500 hover:text-red-600 cursor-pointer whitespace-nowrap">退出所有其他设备</button>
              <button onClick={() => setShowDevicesModal(false)} className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap">关闭</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
