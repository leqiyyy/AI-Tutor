import { useEffect, useState, type ChangeEvent } from 'react';
import { settingsService } from '@/services/settings';
import type {
  DeviceSession,
  StudentAcademicSettings,
  StudentLearningPreferences,
  StudentNotificationSettings,
  StudentPrivacySettings,
  StudentProfileSettings,
} from '@/types/settings';

type ProfileForm = StudentProfileSettings;
type AcademicForm = StudentAcademicSettings;
type PasswordForm = {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
};
type NotificationSettings = StudentNotificationSettings;
type LearningPrefs = StudentLearningPreferences;
type PrivacySettings = StudentPrivacySettings;

const SECTION_TABS = [
  { id: 'profile', label: '基本信息', icon: 'ri-user-line' },
  { id: 'academic', label: '学籍信息', icon: 'ri-id-card-line' },
  { id: 'learning', label: '学习偏好', icon: 'ri-book-open-line' },
  { id: 'security', label: '安全设置', icon: 'ri-shield-line' },
  { id: 'notification', label: '通知偏好', icon: 'ri-notification-line' },
  { id: 'privacy', label: '隐私设置', icon: 'ri-eye-line' },
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
  qq: '',
  hometown: '',
};

const EMPTY_ACADEMIC_FORM: AcademicForm = {
  studentId: '',
  school: '',
  college: '',
  major: '',
  grade: '',
  classNumber: '',
  enrollYear: '',
  expectedGradYear: '',
  degree: '',
  studentType: 'undergraduate',
  dormitory: '',
  advisor: '',
  gpa: '',
  credits: '',
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
  deadlineRemind: false,
  teacherReply: false,
  aiSuggestion: false,
  examRemind: false,
  scoreRelease: false,
};

const EMPTY_LEARNING_PREFS: LearningPrefs = {
  preferStyle: 'visual',
  dailyGoal: '1',
  showLeaderboard: false,
  weeklyReport: false,
  aiAutoSuggest: false,
};

const EMPTY_PRIVACY_SETTINGS: PrivacySettings = {
  showGrade: false,
  showLeaderboard: false,
  showBio: false,
  showContact: false,
  allowAIAnalyze: false,
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

export default function StudentSettings() {
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
  const [interestInput, setInterestInput] = useState('');
  const [devices, setDevices] = useState<DeviceSession[]>([]);

  const [profileForm, setProfileForm] = useState<ProfileForm>(EMPTY_PROFILE_FORM);
  const [academicForm, setAcademicForm] = useState<AcademicForm>(EMPTY_ACADEMIC_FORM);
  const [passwordForm, setPasswordForm] = useState<PasswordForm>(EMPTY_PASSWORD_FORM);
  const [notificationSettings, setNotificationSettings] = useState<NotificationSettings>(EMPTY_NOTIFICATION_SETTINGS);
  const [learningPrefs, setLearningPrefs] = useState<LearningPrefs>(EMPTY_LEARNING_PREFS);
  const [interests, setInterests] = useState<string[]>([]);
  const [privacySettings, setPrivacySettings] = useState<PrivacySettings>(EMPTY_PRIVACY_SETTINGS);

  useEffect(() => {
    let mounted = true;

    const loadSettings = async () => {
      try {
        setErrorMessage('');
        const [settings, deviceSessions] = await Promise.all([
          settingsService.getStudentSettings(),
          settingsService.getDevices(),
        ]);

        if (!mounted) {
          return;
        }

        setProfileForm(settings.profile);
        setAcademicForm(settings.academic);
        setNotificationSettings(settings.notifications);
        setLearningPrefs(settings.learning);
        setPrivacySettings(settings.privacy);
        setInterests(settings.interests);
        setAvatarPreview(settings.avatarUrl ?? '');
        setDevices(deviceSessions);
      } catch (error) {
        if (mounted) {
          setErrorMessage(error instanceof Error ? error.message : '个人设置加载失败，请稍后重试');
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

      const updated = await settingsService.updateStudentSettings({
        profile: profileForm,
        academic: academicForm,
        notifications: notificationSettings,
        learning: learningPrefs,
        privacy: privacySettings,
        interests,
        avatarUrl: avatarPreview || undefined,
      });

      setProfileForm(updated.profile);
      setAcademicForm(updated.academic);
      setNotificationSettings(updated.notifications);
      setLearningPrefs(updated.learning);
      setPrivacySettings(updated.privacy);
      setInterests(updated.interests);
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

  const handleAddInterest = () => {
    const tag = interestInput.trim();
    if (tag && !interests.includes(tag) && interests.length < 10) {
      setInterests(prev => [...prev, tag]);
      setInterestInput('');
    }
  };

  const handleRemoveInterest = (tag: string) => {
    setInterests(prev => prev.filter(t => t !== tag));
  };

  const inputClass = 'w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white transition-colors';
  const labelClass = 'block text-sm font-medium text-gray-700 mb-1.5';

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="rounded-xl border border-gray-200 bg-white px-6 py-10 text-center text-sm text-gray-500">
          正在加载个人设置...
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* 页面标题 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">个人设置</h1>
        <p className="text-sm text-gray-500 mt-1">管理您的个人信息、学籍资料和学习偏好</p>
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
                  李
                </div>
              )}
              <label
                htmlFor="avatar-upload-student"
                className="absolute bottom-0 right-0 w-6 h-6 bg-teal-500 rounded-full flex items-center justify-center cursor-pointer hover:bg-teal-600 transition-colors"
              >
                <i className="ri-camera-line text-white text-xs"></i>
              </label>
              <input type="file" id="avatar-upload-student" accept="image/*" onChange={handleAvatarUpload} className="hidden" />
            </div>
            <div className="text-sm font-semibold text-gray-900">{profileForm.name}</div>
            <div className="text-xs text-gray-500 mt-0.5">{academicForm.major}</div>
            <div className="mt-2 px-2 py-1 bg-teal-50 rounded-full text-xs text-teal-600 font-medium">
              学号 {academicForm.studentId}
            </div>
            {/* 学业概览 */}
            <div className="mt-3 grid grid-cols-2 gap-2">
              <div className="p-2 bg-gray-50 rounded-lg">
                <div className="text-sm font-bold text-gray-900">{academicForm.gpa}</div>
                <div className="text-xs text-gray-500">GPA</div>
              </div>
              <div className="p-2 bg-gray-50 rounded-lg">
                <div className="text-sm font-bold text-gray-900">{academicForm.credits}</div>
                <div className="text-xs text-gray-500">已修学分</div>
              </div>
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
                    <input type="text" value={profileForm.name} onChange={e => setProfileForm({ ...profileForm, name: e.target.value })} className={inputClass} placeholder="请输入姓名" />
                  </div>
                  <div>
                    <label className={labelClass}>姓名（英文/拼音）</label>
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
                  <div className="col-span-2">
                    <label className={labelClass}>家乡</label>
                    <input type="text" value={profileForm.hometown} onChange={e => setProfileForm({ ...profileForm, hometown: e.target.value })} className={inputClass} placeholder="请输入您的家乡" />
                  </div>
                </div>

                <div className="mt-4">
                  <label className={labelClass}>个人简介</label>
                  <textarea
                    rows={4}
                    value={profileForm.bio}
                    onChange={e => setProfileForm({ ...profileForm, bio: e.target.value })}
                    placeholder="介绍一下自己，分享您的学习目标和兴趣爱好..."
                    className={inputClass + ' resize-none'}
                    maxLength={300}
                  />
                  <div className="text-xs text-gray-400 text-right mt-1">{profileForm.bio.length}/300</div>
                </div>

                {/* 兴趣标签 */}
                <div className="mt-4">
                  <label className={labelClass}>兴趣标签</label>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {interests.map(tag => (
                      <span
                        key={tag}
                        className="flex items-center gap-1 px-3 py-1 bg-teal-50 text-teal-700 text-xs rounded-full font-medium group"
                      >
                        {tag}
                        <button
                          onClick={() => handleRemoveInterest(tag)}
                          className="w-3 h-3 flex items-center justify-center text-teal-400 hover:text-teal-700 cursor-pointer"
                        >
                          <i className="ri-close-line text-xs"></i>
                        </button>
                      </span>
                    ))}
                    {interests.length < 10 && (
                      <div className="flex items-center gap-1">
                        <input
                          type="text"
                          value={interestInput}
                          onChange={e => setInterestInput(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && handleAddInterest()}
                          placeholder="添加标签..."
                          className="px-2 py-1 text-xs border border-dashed border-gray-300 rounded-full focus:outline-none focus:border-teal-400 w-24"
                        />
                        <button
                          onClick={handleAddInterest}
                          className="w-6 h-6 flex items-center justify-center bg-teal-50 text-teal-600 rounded-full hover:bg-teal-100 cursor-pointer"
                        >
                          <i className="ri-add-line text-xs"></i>
                        </button>
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-gray-400">最多添加10个标签，按 Enter 或点击加号确认</p>
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
                    <input type="email" value={profileForm.email} onChange={e => setProfileForm({ ...profileForm, email: e.target.value })} className={inputClass} placeholder="请输入邮箱" />
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
                      <i className="ri-qq-line mr-1 text-gray-400"></i>QQ 号
                    </label>
                    <input type="text" value={profileForm.qq} onChange={e => setProfileForm({ ...profileForm, qq: e.target.value })} className={inputClass} placeholder="请输入QQ号" />
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed">保存修改</button>
              </div>
            </>
          )}

          {/* ===== 学籍信息 ===== */}
          {activeSection === 'academic' && (
            <>
              {/* 学籍概览卡片 */}
              <div className="bg-gradient-to-r from-teal-500 to-teal-600 rounded-xl p-6 text-white">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-sm opacity-80 mb-1">在籍学生</div>
                    <div className="text-2xl font-bold mb-1">{profileForm.name}</div>
                    <div className="text-sm opacity-90">{academicForm.school} · {academicForm.college}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm opacity-80 mb-1">学号</div>
                    <div className="text-xl font-mono font-bold">{academicForm.studentId}</div>
                    <div className="text-xs opacity-70 mt-1">{academicForm.enrollYear} 级 · {academicForm.classNumber}</div>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-4 gap-4">
                  {[
                    { label: '已修学分', value: academicForm.credits },
                    { label: 'GPA', value: academicForm.gpa },
                    { label: '预计毕业', value: academicForm.expectedGradYear },
                    { label: '学制', value: '4年' },
                  ].map((item, idx) => (
                    <div key={idx} className="bg-white/15 rounded-lg p-2 text-center">
                      <div className="text-base font-bold">{item.value}</div>
                      <div className="text-xs opacity-80 mt-0.5">{item.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-teal-50">
                    <i className="ri-id-card-line text-teal-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">学籍基本信息</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>学号</label>
                    <div className="relative">
                      <input
                        type="text"
                        value={academicForm.studentId}
                        readOnly
                        className={inputClass + ' bg-gray-50 text-gray-500 pr-10 cursor-not-allowed'}
                      />
                      <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center">
                        <i className="ri-lock-line text-gray-400 text-sm"></i>
                      </div>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">学号由学校统一分配，如需修改请联系教务处</p>
                  </div>
                  <div>
                    <label className={labelClass}>学生类型</label>
                    <select value={academicForm.studentType} onChange={e => setAcademicForm({ ...academicForm, studentType: e.target.value })} className={inputClass + ' cursor-pointer'}>
                      <option value="undergraduate">本科生</option>
                      <option value="master">硕士研究生</option>
                      <option value="phd">博士研究生</option>
                      <option value="exchange">交换生</option>
                      <option value="international">留学生</option>
                    </select>
                  </div>
                  <div>
                    <label className={labelClass}>所在学校</label>
                    <input type="text" value={academicForm.school} onChange={e => setAcademicForm({ ...academicForm, school: e.target.value })} className={inputClass} placeholder="请输入学校全称" />
                  </div>
                  <div>
                    <label className={labelClass}>所在学院</label>
                    <input type="text" value={academicForm.college} onChange={e => setAcademicForm({ ...academicForm, college: e.target.value })} className={inputClass} placeholder="请输入学院名称" />
                  </div>
                  <div>
                    <label className={labelClass}>专业</label>
                    <input type="text" value={academicForm.major} onChange={e => setAcademicForm({ ...academicForm, major: e.target.value })} className={inputClass} placeholder="请输入专业名称" />
                  </div>
                  <div>
                    <label className={labelClass}>攻读学位</label>
                    <select value={academicForm.degree} onChange={e => setAcademicForm({ ...academicForm, degree: e.target.value })} className={inputClass + ' cursor-pointer'}>
                      <option value="工学学士">工学学士</option>
                      <option value="理学学士">理学学士</option>
                      <option value="文学学士">文学学士</option>
                      <option value="法学学士">法学学士</option>
                      <option value="工学硕士">工学硕士</option>
                      <option value="理学硕士">理学硕士</option>
                      <option value="工学博士">工学博士</option>
                      <option value="理学博士">理学博士</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-orange-50">
                    <i className="ri-calendar-line text-orange-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">年级与班级</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>年级</label>
                    <select value={academicForm.grade} onChange={e => setAcademicForm({ ...academicForm, grade: e.target.value })} className={inputClass + ' cursor-pointer'}>
                      <option value="2024">2024级（大一）</option>
                      <option value="2023">2023级（大二）</option>
                      <option value="2022">2022级（大三）</option>
                      <option value="2021">2021级（大四）</option>
                      <option value="2020">2020级（大五及以上）</option>
                    </select>
                  </div>
                  <div>
                    <label className={labelClass}>班级</label>
                    <input type="text" value={academicForm.classNumber} onChange={e => setAcademicForm({ ...academicForm, classNumber: e.target.value })} className={inputClass} placeholder="例如：计科01班" />
                  </div>
                  <div>
                    <label className={labelClass}>入学年份</label>
                    <input
                      type="number"
                      value={academicForm.enrollYear}
                      onChange={e => setAcademicForm({ ...academicForm, enrollYear: e.target.value })}
                      className={inputClass}
                      placeholder="例如：2021"
                      min="2000"
                      max="2030"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>预计毕业年份</label>
                    <input
                      type="number"
                      value={academicForm.expectedGradYear}
                      onChange={e => setAcademicForm({ ...academicForm, expectedGradYear: e.target.value })}
                      className={inputClass}
                      placeholder="例如：2025"
                      min="2000"
                      max="2035"
                    />
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-green-50">
                    <i className="ri-home-3-line text-green-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">在校信息</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>宿舍地址</label>
                    <input type="text" value={academicForm.dormitory} onChange={e => setAcademicForm({ ...academicForm, dormitory: e.target.value })} className={inputClass} placeholder="例如：桂园3舍 306室" />
                  </div>
                  <div>
                    <label className={labelClass}>指导老师</label>
                    <input type="text" value={academicForm.advisor} onChange={e => setAcademicForm({ ...academicForm, advisor: e.target.value })} className={inputClass} placeholder="请输入指导老师姓名" />
                  </div>
                  <div>
                    <label className={labelClass}>当前 GPA</label>
                    <input
                      type="number"
                      value={academicForm.gpa}
                      onChange={e => setAcademicForm({ ...academicForm, gpa: e.target.value })}
                      className={inputClass}
                      placeholder="例如：3.82"
                      step="0.01"
                      min="0"
                      max="4"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>已修学分</label>
                    <input
                      type="number"
                      value={academicForm.credits}
                      onChange={e => setAcademicForm({ ...academicForm, credits: e.target.value })}
                      className={inputClass}
                      placeholder="请输入已修学分"
                      min="0"
                    />
                  </div>
                </div>
              </div>

              {/* 学业进度可视化 */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-blue-50">
                    <i className="ri-bar-chart-line text-blue-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">学业进度概览</h2>
                </div>
                <div className="grid grid-cols-2 gap-5">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">学分完成进度</span>
                      <span className="text-sm font-semibold text-gray-900">127 / 160 学分</span>
                    </div>
                    <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-teal-500 rounded-full" style={{ width: '79%' }}></div>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">已完成 79%，还需 33 学分</div>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-600">在读年限进度</span>
                      <span className="text-sm font-semibold text-gray-900">第3年 / 共4年</span>
                    </div>
                    <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-orange-400 rounded-full" style={{ width: '75%' }}></div>
                    </div>
                    <div className="text-xs text-gray-400 mt-1">已读 75%，预计 2025 年毕业</div>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-4 gap-3">
                  {[
                    { label: '必修课', value: '86', total: '96', color: 'teal' },
                    { label: '专业选修', value: '24', total: '32', color: 'blue' },
                    { label: '公共选修', value: '12', total: '20', color: 'orange' },
                    { label: '实践环节', value: '5', total: '12', color: 'green' },
                  ].map((item, idx) => (
                    <div key={idx} className="p-3 bg-gray-50 rounded-xl text-center">
                      <div className={`text-base font-bold ${
                        item.color === 'teal' ? 'text-teal-600' :
                        item.color === 'blue' ? 'text-blue-600' :
                        item.color === 'orange' ? 'text-orange-600' : 'text-green-600'
                      }`}>{item.value}<span className="text-xs text-gray-400 font-normal">/{item.total}</span></div>
                      <div className="text-xs text-gray-500 mt-0.5">{item.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed">保存修改</button>
              </div>
            </>
          )}

          {/* ===== 学习偏好 ===== */}
          {activeSection === 'learning' && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-teal-50">
                    <i className="ri-book-open-line text-teal-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">学习风格</h2>
                </div>

                <div>
                  <label className={labelClass}>偏好的学习方式</label>
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { value: 'visual', label: '可视化学习', desc: '偏好图表、流程图、思维导图辅助理解', icon: 'ri-eye-line' },
                      { value: 'reading', label: '阅读文字型', desc: '偏好详细的文字说明和理论推导', icon: 'ri-article-line' },
                      { value: 'practice', label: '实践动手型', desc: '偏好通过编程练习和实验理解', icon: 'ri-code-line' },
                      { value: 'discussion', label: '讨论交流型', desc: '偏好在问答和讨论中加深理解', icon: 'ri-discuss-line' },
                    ].map(style => (
                      <button
                        key={style.value}
                        onClick={() => setLearningPrefs(prev => ({ ...prev, preferStyle: style.value }))}
                        className={`p-4 border-2 rounded-xl text-left transition-all cursor-pointer ${
                          learningPrefs.preferStyle === style.value
                            ? 'border-teal-500 bg-teal-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <div className={`w-7 h-7 flex items-center justify-center rounded-lg ${
                            learningPrefs.preferStyle === style.value ? 'bg-teal-100' : 'bg-gray-100'
                          }`}>
                            <i className={`${style.icon} text-sm ${learningPrefs.preferStyle === style.value ? 'text-teal-600' : 'text-gray-600'}`}></i>
                          </div>
                          <div className={`text-sm font-medium ${learningPrefs.preferStyle === style.value ? 'text-teal-700' : 'text-gray-900'}`}>{style.label}</div>
                        </div>
                        <div className="text-xs text-gray-500">{style.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mt-5">
                  <label className={labelClass}>每日学习目标（小时）</label>
                  <div className="flex items-center gap-4">
                    {['1', '2', '3', '4', '5'].map(h => (
                      <button
                        key={h}
                        onClick={() => setLearningPrefs(prev => ({ ...prev, dailyGoal: h }))}
                        className={`w-12 h-12 rounded-xl text-sm font-bold transition-colors cursor-pointer flex items-center justify-center flex-col ${
                          learningPrefs.dailyGoal === h
                            ? 'bg-teal-500 text-white'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        {h}
                        <span className="text-xs font-normal opacity-70">时</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-orange-50">
                    <i className="ri-settings-3-line text-orange-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">功能偏好</h2>
                </div>

                <div className="space-y-4">
                  {[
                    { key: 'showLeaderboard', label: '显示学习排行榜', desc: '在课程中展示学习时长等排名信息，激励学习' },
                    { key: 'weeklyReport', label: '接收每周学习报告', desc: '每周一发送上周学习情况汇总' },
                    { key: 'aiAutoSuggest', label: 'AI 自动学习建议', desc: '根据学习数据自动生成个性化复习建议' },
                  ].map(item => (
                    <div key={item.key} className="flex items-center justify-between p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{item.label}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{item.desc}</div>
                      </div>
                      <button
                        onClick={() => setLearningPrefs(prev => ({ ...prev, [item.key]: !prev[item.key as keyof LearningPrefs] }))}
                        className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer flex-shrink-0 ${
                          learningPrefs[item.key as keyof LearningPrefs] ? 'bg-teal-500' : 'bg-gray-200'
                        }`}
                      >
                        <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                          learningPrefs[item.key as keyof LearningPrefs] ? 'translate-x-5' : 'translate-x-0'
                        }`}></span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed">保存偏好</button>
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
                        <div className="text-xs text-gray-500 mt-0.5">上次修改：45天前 · 建议每学期修改一次</div>
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
                          {twoFAEnabled ? '已开启 · 登录时需要验证码' : '未开启 · 开启可提升账号安全性'}
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

              {/* 登录设备 */}
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
                    <div className="text-xs text-gray-500 mt-0.5">注销后所有学习记录将被删除，此操作不可撤销</div>
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
                    <div key={item.key} className="flex items-center justify-between p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
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
                    { key: 'deadlineRemind', label: '作业截止提醒', desc: '作业截止前3小时和24小时发送提醒', icon: 'ri-time-line', color: 'red' },
                    { key: 'teacherReply', label: '教师回复', desc: '教师回复了您的提问或评论', icon: 'ri-chat-3-line', color: 'teal' },
                    { key: 'aiSuggestion', label: 'AI学习建议', desc: 'AI检测到薄弱知识点时推送复习建议', icon: 'ri-lightbulb-line', color: 'orange' },
                    { key: 'examRemind', label: '考试提醒', desc: '考试开始前24小时和1小时发送提醒', icon: 'ri-file-list-3-line', color: 'blue' },
                    { key: 'scoreRelease', label: '成绩发布通知', desc: '作业或考试成绩公布后立即通知', icon: 'ri-trophy-line', color: 'green' },
                  ].map(item => (
                    <div key={item.key} className="flex items-center justify-between p-3 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 flex items-center justify-center rounded-lg ${
                          item.color === 'red' ? 'bg-red-50' :
                          item.color === 'teal' ? 'bg-teal-50' :
                          item.color === 'orange' ? 'bg-orange-50' :
                          item.color === 'blue' ? 'bg-blue-50' : 'bg-green-50'
                        }`}>
                          <i className={`${item.icon} text-sm ${
                            item.color === 'red' ? 'text-red-600' :
                            item.color === 'teal' ? 'text-teal-600' :
                            item.color === 'orange' ? 'text-orange-600' :
                            item.color === 'blue' ? 'text-blue-600' : 'text-green-600'
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

          {/* ===== 隐私设置 ===== */}
          {activeSection === 'privacy' && (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-teal-50">
                    <i className="ri-eye-line text-teal-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">信息可见性</h2>
                </div>
                <p className="text-xs text-gray-500 mb-5 ml-9">控制哪些信息可以被同班同学或教师看到</p>

                <div className="space-y-4">
                  {[
                    { key: 'showGrade', label: '成绩对同学可见', desc: '关闭后其他同学看不到您的成绩和排名', icon: 'ri-trophy-line', color: 'orange' },
                    { key: 'showLeaderboard', label: '出现在学习排行榜', desc: '关闭后将从课程学习时长排行榜中隐藏', icon: 'ri-bar-chart-line', color: 'blue' },
                    { key: 'showBio', label: '个人简介对外可见', desc: '其他用户访问您的主页时可以看到简介', icon: 'ri-user-line', color: 'teal' },
                    { key: 'showContact', label: '联系方式对同学可见', desc: '关闭后手机、微信等联系方式将被隐藏', icon: 'ri-contacts-line', color: 'green' },
                  ].map(item => (
                    <div key={item.key} className="flex items-center justify-between p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className={`w-8 h-8 flex items-center justify-center rounded-lg ${
                          item.color === 'orange' ? 'bg-orange-50' :
                          item.color === 'blue' ? 'bg-blue-50' :
                          item.color === 'teal' ? 'bg-teal-50' : 'bg-green-50'
                        }`}>
                          <i className={`${item.icon} text-sm ${
                            item.color === 'orange' ? 'text-orange-600' :
                            item.color === 'blue' ? 'text-blue-600' :
                            item.color === 'teal' ? 'text-teal-600' : 'text-green-600'
                          }`}></i>
                        </div>
                        <div>
                          <div className="text-sm font-medium text-gray-900">{item.label}</div>
                          <div className="text-xs text-gray-500 mt-0.5">{item.desc}</div>
                        </div>
                      </div>
                      <button
                        onClick={() => setPrivacySettings(prev => ({ ...prev, [item.key]: !prev[item.key as keyof typeof privacySettings] }))}
                        className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer flex-shrink-0 ${
                          privacySettings[item.key as keyof typeof privacySettings] ? 'bg-teal-500' : 'bg-gray-200'
                        }`}
                      >
                        <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                          privacySettings[item.key as keyof typeof privacySettings] ? 'translate-x-5' : 'translate-x-0'
                        }`}></span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center gap-2 mb-5">
                  <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-purple-50">
                    <i className="ri-robot-line text-purple-600 text-sm"></i>
                  </div>
                  <h2 className="text-base font-semibold text-gray-900">数据使用授权</h2>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 border border-gray-100 rounded-lg hover:border-gray-200 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-purple-50">
                        <i className="ri-brain-line text-purple-600 text-sm"></i>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-900">允许 AI 分析学习数据</div>
                        <div className="text-xs text-gray-500 mt-0.5">AI 将分析您的学习行为，提供个性化建议和知识图谱</div>
                      </div>
                    </div>
                    <button
                      onClick={() => setPrivacySettings(prev => ({ ...prev, allowAIAnalyze: !prev.allowAIAnalyze }))}
                      className={`relative w-11 h-6 rounded-full transition-colors cursor-pointer flex-shrink-0 ${
                        privacySettings.allowAIAnalyze ? 'bg-teal-500' : 'bg-gray-200'
                      }`}
                    >
                      <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                        privacySettings.allowAIAnalyze ? 'translate-x-5' : 'translate-x-0'
                      }`}></span>
                    </button>
                  </div>
                </div>

                <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-start gap-2">
                    <i className="ri-information-line text-gray-400 text-base flex-shrink-0 mt-0.5"></i>
                    <p className="text-xs text-gray-500 leading-relaxed">
                      我们承诺：您的学习数据仅用于平台功能优化和个性化推荐，不会出售给第三方，您可随时在此页面撤销数据使用授权。
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={handleSave} disabled={isSaving} className="px-6 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition-colors cursor-pointer whitespace-nowrap disabled:opacity-60 disabled:cursor-not-allowed">保存设置</button>
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
                  <div className="p-3 bg-gray-50 rounded-lg text-left">
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
