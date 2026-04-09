import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

type Role = 'student' | 'teacher';

type StudentForm = {
  realName: string;
  studentId: string;
  email: string;
  phone: string;
  school: string;
  college: string;
  major: string;
  grade: string;
  classNo: string;
  password: string;
  confirmPassword: string;
  verifyCode: string;
  agree: boolean;
};

type TeacherForm = {
  realName: string;
  teacherId: string;
  email: string;
  phone: string;
  school: string;
  college: string;
  department: string;
  title: string;
  idCardNo: string;
  certFile: string;
  password: string;
  confirmPassword: string;
  verifyCode: string;
  agree: boolean;
};

const gradeOptions = ['2021级', '2022级', '2023级', '2024级', '2025级'];
const titleOptions = ['助教', '讲师', '副教授', '教授', '研究员', '副研究员'];

export default function RegisterPage() {
  const navigate = useNavigate();
  const [role, setRole] = useState<Role>('student');
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [codeSent, setCodeSent] = useState(false);
  const [codeCountdown, setCodeCountdown] = useState(0);

  const [studentForm, setStudentForm] = useState<StudentForm>({
    realName: '', studentId: '', email: '', phone: '',
    school: '', college: '', major: '', grade: '', classNo: '',
    password: '', confirmPassword: '', verifyCode: '', agree: false,
  });

  const [teacherForm, setTeacherForm] = useState<TeacherForm>({
    realName: '', teacherId: '', email: '', phone: '',
    school: '', college: '', department: '', title: '',
    idCardNo: '', certFile: '', password: '', confirmPassword: '', verifyCode: '', agree: false,
  });

  const [showPwd, setShowPwd] = useState(false);
  const [showConfirmPwd, setShowConfirmPwd] = useState(false);

  const updateStudent = (field: keyof StudentForm, value: string | boolean) => {
    setStudentForm(prev => ({ ...prev, [field]: value }));
    setErrors(prev => { const n = { ...prev }; delete n[field]; return n; });
  };

  const updateTeacher = (field: keyof TeacherForm, value: string | boolean) => {
    setTeacherForm(prev => ({ ...prev, [field]: value }));
    setErrors(prev => { const n = { ...prev }; delete n[field]; return n; });
  };

  const currentEmail = role === 'student' ? studentForm.email : teacherForm.email;

  const handleSendCode = () => {
    if (!currentEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(currentEmail)) {
      setErrors(prev => ({ ...prev, verifyCode: '请先在第一步填写正确的邮箱地址' }));
      return;
    }
    // TODO: POST /api/auth/send-verify-code { email: currentEmail }
    setCodeSent(true);
    setCodeCountdown(60);
    const timer = setInterval(() => {
      setCodeCountdown(prev => {
        if (prev <= 1) { clearInterval(timer); return 0; }
        return prev - 1;
      });
    }, 1000);
  };

  const validateStep1 = () => {
    const errs: Record<string, string> = {};
    if (role === 'student') {
      if (!studentForm.realName.trim()) errs.realName = '请输入真实姓名';
      if (!studentForm.studentId.trim()) errs.studentId = '请输入学号';
      if (!studentForm.email.trim()) errs.email = '请输入邮箱';
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(studentForm.email)) errs.email = '邮箱格式不正确';
      if (!studentForm.phone.trim()) errs.phone = '请输入手机号';
      else if (!/^1[3-9]\d{9}$/.test(studentForm.phone)) errs.phone = '手机号格式不正确';
    } else {
      if (!teacherForm.realName.trim()) errs.realName = '请输入真实姓名';
      if (!teacherForm.teacherId.trim()) errs.teacherId = '请输入工号';
      if (!teacherForm.email.trim()) errs.email = '请输入邮箱';
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(teacherForm.email)) errs.email = '邮箱格式不正确';
      if (!teacherForm.phone.trim()) errs.phone = '请输入手机号';
      else if (!/^1[3-9]\d{9}$/.test(teacherForm.phone)) errs.phone = '手机号格式不正确';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const validateStep2 = () => {
    const errs: Record<string, string> = {};
    if (role === 'student') {
      if (!studentForm.school.trim()) errs.school = '请输入学校名称';
      if (!studentForm.college.trim()) errs.college = '请输入学院';
      if (!studentForm.major.trim()) errs.major = '请输入专业';
      if (!studentForm.grade) errs.grade = '请选择年级';
    } else {
      if (!teacherForm.school.trim()) errs.school = '请输入学校名称';
      if (!teacherForm.college.trim()) errs.college = '请输入学院';
      if (!teacherForm.department.trim()) errs.department = '请输入系所';
      if (!teacherForm.title) errs.title = '请选择职称';
      if (!teacherForm.idCardNo.trim()) errs.idCardNo = '请输入身份证号';
      else if (!/^\d{17}[\dXx]$/.test(teacherForm.idCardNo)) errs.idCardNo = '身份证号格式不正确';
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const validateStep3 = () => {
    const errs: Record<string, string> = {};
    const pwd = role === 'student' ? studentForm.password : teacherForm.password;
    const confirmPwd = role === 'student' ? studentForm.confirmPassword : teacherForm.confirmPassword;
    const agree = role === 'student' ? studentForm.agree : teacherForm.agree;
    if (!pwd) errs.password = '请设置密码';
    else if (pwd.length < 8) errs.password = '密码不少于8位';
    else if (!/(?=.*[a-zA-Z])(?=.*\d)/.test(pwd)) errs.password = '密码需包含字母和数字';
    if (!confirmPwd) errs.confirmPassword = '请确认密码';
    else if (pwd !== confirmPwd) errs.confirmPassword = '两次密码不一致';
    if (!agree) errs.agree = '请阅读并同意用户协议';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleNext = () => {
    if (step === 1) {
      if (validateStep1()) setStep(2);
    } else if (step === 2) {
      if (validateStep2()) setStep(3);
    }
  };

  const handleBack = () => {
    setErrors({});
    setStep(prev => prev - 1);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateStep3()) return;
    setLoading(true);

    // TODO: POST /api/auth/register
    const formData = new URLSearchParams();
    if (role === 'student') {
      formData.append('role', '学生');
      formData.append('realName', studentForm.realName);
      formData.append('studentId', studentForm.studentId);
      formData.append('email', studentForm.email);
      formData.append('phone', studentForm.phone);
      formData.append('school', studentForm.school);
      formData.append('college', studentForm.college);
      formData.append('major', studentForm.major);
      formData.append('grade', studentForm.grade);
      formData.append('classNo', studentForm.classNo);
    } else {
      formData.append('role', '教师');
      formData.append('realName', teacherForm.realName);
      formData.append('teacherId', teacherForm.teacherId);
      formData.append('email', teacherForm.email);
      formData.append('phone', teacherForm.phone);
      formData.append('school', teacherForm.school);
      formData.append('college', teacherForm.college);
      formData.append('department', teacherForm.department);
      formData.append('title', teacherForm.title);
      formData.append('idCardNo', teacherForm.idCardNo);
    }

    const submitUrl = role === 'student'
      ? 'https://readdy.ai/api/form/d6pvo36a739gopmlh1ag'
      : 'https://readdy.ai/api/form/d6pvo3ma739gopmlh1b0';

    try {
      await fetch(submitUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      });
      setSubmitted(true);
    } catch {
      setErrors({ submit: '提交失败，请稍后重试' });
    } finally {
      setLoading(false);
    }
  };

  const btnClass = role === 'student'
    ? 'bg-teal-600 hover:bg-teal-700'
    : 'bg-orange-500 hover:bg-orange-600';
  const ringClass = role === 'student' ? 'focus:ring-teal-500' : 'focus:ring-orange-500';
  const textAccent = role === 'student' ? 'text-teal-600' : 'text-orange-500';
  const bgAccent = role === 'student' ? 'bg-teal-50' : 'bg-orange-50';
  const borderAccentColor = role === 'student' ? 'border-teal-200' : 'border-orange-200';

  const inputClass = `w-full pl-9 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 ${ringClass} focus:border-transparent transition-all`;
  const selectClass = `w-full pl-9 pr-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 ${ringClass} focus:border-transparent transition-all bg-white appearance-none`;

  const steps = ['基本信息', role === 'student' ? '学籍信息' : '任职信息', '账号安全'];

  const getPwdStrength = (pwd: string) => {
    if (!pwd) return 0;
    if (pwd.length >= 12 && /[A-Z]/.test(pwd) && /\d/.test(pwd) && /[^a-zA-Z0-9]/.test(pwd)) return 4;
    if (pwd.length >= 10 && /[a-zA-Z]/.test(pwd) && /\d/.test(pwd)) return 3;
    if (pwd.length >= 8 && /[a-zA-Z]/.test(pwd) && /\d/.test(pwd)) return 2;
    return 1;
  };

  const strengthLabels = ['', '弱', '一般', '强', '非常强'];
  const strengthColors = ['', 'bg-red-400', 'bg-yellow-400', 'bg-teal-400', 'bg-green-500'];

  if (submitted) {
    return (
      <div className="min-h-screen flex" style={{ fontFamily: "'Noto Sans SC', sans-serif" }}>
        <div className="hidden lg:flex lg:w-[52%] relative flex-col justify-between overflow-hidden">
          <img
            src="https://readdy.ai/api/search-image?query=Beautiful%20Chinese%20university%20campus%20cherry%20blossom%20trees%20in%20full%20bloom%20along%20a%20serene%20pathway%20with%20modern%20academic%20buildings%20in%20the%20background%2C%20soft%20warm%20spring%20light%20filtering%20through%20pink%20petals%2C%20elegant%20and%20peaceful%20atmosphere%2C%20high%20quality%20photography%20style%20with%20shallow%20depth%20of%20field%2C%20pastel%20pink%20and%20white%20tones%2C%20professional%20educational%20institution%20aesthetic&width=900&height=1080&seq=login-bg-1&orientation=portrait"
            alt="珞樱学堂"
            className="absolute inset-0 w-full h-full object-cover object-top"
          />
          <div className="absolute inset-0 bg-gradient-to-br from-teal-900/70 via-teal-800/50 to-teal-600/40"></div>
          <div className="relative z-10 p-10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                <i className="ri-plant-line text-white text-xl"></i>
              </div>
              <span className="text-2xl font-bold text-white tracking-wide">珞樱学堂</span>
            </div>
          </div>
          <div className="relative z-10 px-10 pb-16">
            <h2 className="text-3xl font-bold text-white mb-3">注册申请已提交</h2>
            <p className="text-white/75 text-sm leading-relaxed">管理员将在1-3个工作日内完成审核，审核结果将通过邮件通知您。</p>
          </div>
        </div>
        <div className="flex-1 flex flex-col justify-center items-center bg-white px-8">
          <div className="w-full max-w-md text-center">
            <div className={`w-20 h-20 rounded-full ${bgAccent} flex items-center justify-center mx-auto mb-6`}>
              <i className={`ri-checkbox-circle-line text-4xl ${textAccent}`}></i>
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">申请已提交！</h3>
            <p className="text-sm text-gray-500 mb-2">
              您的<span className="font-medium text-gray-700">{role === 'student' ? '学生' : '教师'}</span>注册申请已成功提交
            </p>
            <p className="text-sm text-gray-400 mb-8">管理员审核通过后，您将收到邮件通知，届时即可登录使用。</p>
            <div className={`rounded-xl border ${borderAccentColor} ${bgAccent} p-4 mb-8 text-left`}>
              <div className="flex items-start gap-3">
                <i className={`ri-information-line text-base mt-0.5 ${textAccent}`}></i>
                <div className="text-xs text-gray-600 leading-relaxed">
                  <p className="font-medium text-gray-700 mb-1">温馨提示</p>
                  <p>· 审核周期：1-3个工作日</p>
                  <p>· 审核结果将发送至您填写的邮箱</p>
                  {role === 'teacher' && <p>· 教师资质审核需核验工号及证件，请确保信息真实</p>}
                  <p>· 如有疑问请联系：support@luoying.edu.cn</p>
                </div>
              </div>
            </div>
            <button
              onClick={() => navigate('/login')}
              className={`w-full py-2.5 text-sm font-semibold text-white rounded-lg transition-all cursor-pointer whitespace-nowrap ${btnClass}`}
            >
              返回登录页
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex" style={{ fontFamily: "'Noto Sans SC', sans-serif" }}>
      {/* 左侧品牌区 */}
      <div className="hidden lg:flex lg:w-[52%] relative flex-col justify-between overflow-hidden">
        <img
          src="https://readdy.ai/api/search-image?query=Beautiful%20Chinese%20university%20campus%20cherry%20blossom%20trees%20in%20full%20bloom%20along%20a%20serene%20pathway%20with%20modern%20academic%20buildings%20in%20the%20background%2C%20soft%20warm%20spring%20light%20filtering%20through%20pink%20petals%2C%20elegant%20and%20peaceful%20atmosphere%2C%20high%20quality%20photography%20style%20with%20shallow%20depth%20of%20field%2C%20pastel%20pink%20and%20white%20tones%2C%20professional%20educational%20institution%20aesthetic&width=900&height=1080&seq=login-bg-1&orientation=portrait"
          alt="珞樱学堂"
          className="absolute inset-0 w-full h-full object-cover object-top"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-teal-900/70 via-teal-800/50 to-teal-600/40"></div>
        <div className="relative z-10 p-10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <i className="ri-plant-line text-white text-xl"></i>
            </div>
            <span className="text-2xl font-bold text-white tracking-wide">珞樱学堂</span>
          </div>
        </div>
        <div className="relative z-10 px-10 pb-4">
          <h1 className="text-4xl font-bold text-white leading-tight mb-4">
            加入珞樱学堂<br />开启智能学习
          </h1>
          <p className="text-white/80 text-base leading-relaxed mb-8">
            填写注册信息，等待管理员审核<br />即可享受AI助教全功能服务
          </p>
          <div className="flex flex-col gap-4">
            {[
              { icon: 'ri-graduation-cap-line', title: '学生注册', desc: '填写学籍信息，加入课程班级，享受AI答疑' },
              { icon: 'ri-user-star-line', title: '教师注册', desc: '提交工号及资质，创建课程，管理学生学习' },
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-white/10 backdrop-blur-sm">
                <div className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/20 shrink-0">
                  <i className={`${item.icon} text-white text-base`}></i>
                </div>
                <div>
                  <div className="text-white text-sm font-semibold">{item.title}</div>
                  <div className="text-white/70 text-xs mt-0.5 leading-relaxed">{item.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="relative z-10 px-10 pb-10">
          <div className="flex items-center gap-6 pt-6 border-t border-white/20">
            {[
              { num: '12,000+', label: '在校学生' },
              { num: '680+', label: '授课教师' },
              { num: '98%', label: '用户满意度' },
            ].map((stat, i) => (
              <div key={i} className="text-center">
                <div className="text-xl font-bold text-white">{stat.num}</div>
                <div className="text-xs text-white/60 mt-0.5">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 右侧注册区 */}
      <div className="flex-1 flex flex-col justify-center items-center bg-white px-8 py-10 overflow-y-auto">
        <div className="w-full max-w-md">
          {/* 移动端 Logo */}
          <div className="flex lg:hidden items-center gap-2 mb-6 justify-center">
            <div className="w-9 h-9 rounded-xl bg-teal-500 flex items-center justify-center">
              <i className="ri-plant-line text-white text-lg"></i>
            </div>
            <span className="text-xl font-bold text-gray-900">珞樱学堂</span>
          </div>

          <div className="mb-5">
            <h2 className="text-2xl font-bold text-gray-900 mb-1">注册账号</h2>
            <p className="text-sm text-gray-500">请选择注册身份并填写相关信息</p>
          </div>

          {/* 角色切换 */}
          <div className="flex gap-2 mb-6 p-1 bg-gray-100 rounded-xl">
            {(['student', 'teacher'] as Role[]).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => { setRole(r); setStep(1); setErrors({}); setCodeSent(false); setCodeCountdown(0); }}
                className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all cursor-pointer whitespace-nowrap ${
                  role === r
                    ? `bg-white shadow-sm ${r === 'student' ? 'text-teal-700' : 'text-orange-600'}`
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <i className={`${r === 'student' ? 'ri-graduation-cap-line' : 'ri-user-star-line'} text-base`}></i>
                {r === 'student' ? '学生注册' : '教师注册'}
              </button>
            ))}
          </div>

          {/* 步骤指示器 */}
          <div className="flex items-center mb-6">
            {steps.map((s, i) => (
              <div key={i} className="flex items-center flex-1">
                <div className="flex flex-col items-center">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                    step > i + 1
                      ? (role === 'student' ? 'bg-teal-500 text-white' : 'bg-orange-500 text-white')
                      : step === i + 1
                      ? (role === 'student' ? 'bg-teal-600 text-white ring-4 ring-teal-100' : 'bg-orange-500 text-white ring-4 ring-orange-100')
                      : 'bg-gray-200 text-gray-400'
                  }`}>
                    {step > i + 1 ? <i className="ri-check-line text-xs"></i> : i + 1}
                  </div>
                  <span className={`text-xs mt-1 whitespace-nowrap ${step === i + 1 ? (role === 'student' ? 'text-teal-600 font-medium' : 'text-orange-500 font-medium') : 'text-gray-400'}`}>{s}</span>
                </div>
                {i < steps.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-2 mb-4 transition-all ${step > i + 1 ? (role === 'student' ? 'bg-teal-400' : 'bg-orange-400') : 'bg-gray-200'}`}></div>
                )}
              </div>
            ))}
          </div>

          {/* 表单区域 */}
          <form onSubmit={handleSubmit} data-readdy-form>

            {/* ===== Step 1: 基本信息 ===== */}
            {step === 1 && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">真实姓名 <span className="text-red-500">*</span></label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-user-line text-sm"></i>
                      </div>
                      <input
                        type="text"
                        name="realName"
                        value={role === 'student' ? studentForm.realName : teacherForm.realName}
                        onChange={e => role === 'student' ? updateStudent('realName', e.target.value) : updateTeacher('realName', e.target.value)}
                        placeholder="请输入真实姓名"
                        className={inputClass}
                      />
                    </div>
                    {errors.realName && <p className="text-xs text-red-500 mt-1">{errors.realName}</p>}
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">
                      {role === 'student' ? '学号' : '工号'} <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-id-card-line text-sm"></i>
                      </div>
                      <input
                        type="text"
                        name={role === 'student' ? 'studentId' : 'teacherId'}
                        value={role === 'student' ? studentForm.studentId : teacherForm.teacherId}
                        onChange={e => role === 'student' ? updateStudent('studentId', e.target.value) : updateTeacher('teacherId', e.target.value)}
                        placeholder={role === 'student' ? '请输入学号' : '请输入工号'}
                        className={inputClass}
                      />
                    </div>
                    {(errors.studentId || errors.teacherId) && (
                      <p className="text-xs text-red-500 mt-1">{errors.studentId || errors.teacherId}</p>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">邮箱地址 <span className="text-red-500">*</span></label>
                  <div className="relative">
                    <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                      <i className="ri-mail-line text-sm"></i>
                    </div>
                    <input
                      type="email"
                      name="email"
                      value={role === 'student' ? studentForm.email : teacherForm.email}
                      onChange={e => role === 'student' ? updateStudent('email', e.target.value) : updateTeacher('email', e.target.value)}
                      placeholder="请输入常用邮箱（用于接收审核通知）"
                      className={inputClass}
                    />
                  </div>
                  {errors.email && <p className="text-xs text-red-500 mt-1">{errors.email}</p>}
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">手机号码 <span className="text-red-500">*</span></label>
                  <div className="relative">
                    <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                      <i className="ri-smartphone-line text-sm"></i>
                    </div>
                    <input
                      type="tel"
                      name="phone"
                      value={role === 'student' ? studentForm.phone : teacherForm.phone}
                      onChange={e => role === 'student' ? updateStudent('phone', e.target.value) : updateTeacher('phone', e.target.value)}
                      placeholder="请输入手机号码"
                      className={inputClass}
                    />
                  </div>
                  {errors.phone && <p className="text-xs text-red-500 mt-1">{errors.phone}</p>}
                </div>

                <div className={`rounded-lg border p-3 ${borderAccentColor} ${bgAccent}`}>
                  <div className="flex items-start gap-2">
                    <i className={`ri-shield-check-line text-sm mt-0.5 ${textAccent}`}></i>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      您的个人信息将严格保密，仅用于身份核验，不会对外公开。
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* ===== Step 2: 学籍信息（学生）===== */}
            {step === 2 && role === 'student' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">学校名称 <span className="text-red-500">*</span></label>
                  <div className="relative">
                    <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                      <i className="ri-building-line text-sm"></i>
                    </div>
                    <input
                      type="text"
                      name="school"
                      value={studentForm.school}
                      onChange={e => updateStudent('school', e.target.value)}
                      placeholder="如：武汉大学"
                      className={inputClass}
                    />
                  </div>
                  {errors.school && <p className="text-xs text-red-500 mt-1">{errors.school}</p>}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">所在学院 <span className="text-red-500">*</span></label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-community-line text-sm"></i>
                      </div>
                      <input
                        type="text"
                        name="college"
                        value={studentForm.college}
                        onChange={e => updateStudent('college', e.target.value)}
                        placeholder="如：计算机学院"
                        className={inputClass}
                      />
                    </div>
                    {errors.college && <p className="text-xs text-red-500 mt-1">{errors.college}</p>}
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">所学专业 <span className="text-red-500">*</span></label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-book-open-line text-sm"></i>
                      </div>
                      <input
                        type="text"
                        name="major"
                        value={studentForm.major}
                        onChange={e => updateStudent('major', e.target.value)}
                        placeholder="如：计算机科学与技术"
                        className={inputClass}
                      />
                    </div>
                    {errors.major && <p className="text-xs text-red-500 mt-1">{errors.major}</p>}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">入学年级 <span className="text-red-500">*</span></label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-calendar-line text-sm"></i>
                      </div>
                      <select
                        name="grade"
                        value={studentForm.grade}
                        onChange={e => updateStudent('grade', e.target.value)}
                        className={selectClass}
                      >
                        <option value="">请选择年级</option>
                        {gradeOptions.map(g => <option key={g} value={g}>{g}</option>)}
                      </select>
                      <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
                        <i className="ri-arrow-down-s-line text-sm"></i>
                      </div>
                    </div>
                    {errors.grade && <p className="text-xs text-red-500 mt-1">{errors.grade}</p>}
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">班级编号</label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-group-line text-sm"></i>
                      </div>
                      <input
                        type="text"
                        name="classNo"
                        value={studentForm.classNo}
                        onChange={e => updateStudent('classNo', e.target.value)}
                        placeholder="如：01班（选填）"
                        className={inputClass}
                      />
                    </div>
                  </div>
                </div>

                {/* 学生证上传 */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">学生证照片 <span className="text-gray-400 font-normal">（选填）</span></label>
                  <div className="border-2 border-dashed border-teal-200 hover:border-teal-400 hover:bg-teal-50 rounded-lg p-4 text-center cursor-pointer transition-colors">
                    <div className="w-8 h-8 flex items-center justify-center mx-auto mb-2 text-gray-400">
                      <i className="ri-upload-cloud-2-line text-2xl"></i>
                    </div>
                    <p className="text-xs text-gray-500">上传学生证或在读证明</p>
                    <p className="text-xs text-gray-400 mt-0.5">支持 JPG、PNG、PDF，不超过 5MB</p>
                  </div>
                </div>

                <div className={`rounded-lg border p-3 border-teal-200 bg-teal-50`}>
                  <div className="flex items-start gap-2">
                    <i className="ri-information-line text-sm mt-0.5 text-teal-600"></i>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      学籍信息将用于身份核验，请确保与学校教务系统中的信息一致。
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* ===== Step 2: 任职信息（教师）===== */}
            {step === 2 && role === 'teacher' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">学校名称 <span className="text-red-500">*</span></label>
                  <div className="relative">
                    <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                      <i className="ri-building-line text-sm"></i>
                    </div>
                    <input
                      type="text"
                      name="school"
                      value={teacherForm.school}
                      onChange={e => updateTeacher('school', e.target.value)}
                      placeholder="如：武汉大学"
                      className={inputClass}
                    />
                  </div>
                  {errors.school && <p className="text-xs text-red-500 mt-1">{errors.school}</p>}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">所在学院 <span className="text-red-500">*</span></label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-community-line text-sm"></i>
                      </div>
                      <input
                        type="text"
                        name="college"
                        value={teacherForm.college}
                        onChange={e => updateTeacher('college', e.target.value)}
                        placeholder="如：计算机学院"
                        className={inputClass}
                      />
                    </div>
                    {errors.college && <p className="text-xs text-red-500 mt-1">{errors.college}</p>}
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">所在系所 <span className="text-red-500">*</span></label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-organization-chart text-sm"></i>
                      </div>
                      <input
                        type="text"
                        name="department"
                        value={teacherForm.department}
                        onChange={e => updateTeacher('department', e.target.value)}
                        placeholder="如：软件工程系"
                        className={inputClass}
                      />
                    </div>
                    {errors.department && <p className="text-xs text-red-500 mt-1">{errors.department}</p>}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">职称 <span className="text-red-500">*</span></label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-award-line text-sm"></i>
                      </div>
                      <select
                        name="title"
                        value={teacherForm.title}
                        onChange={e => updateTeacher('title', e.target.value)}
                        className={selectClass}
                      >
                        <option value="">请选择职称</option>
                        {titleOptions.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                      <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">
                        <i className="ri-arrow-down-s-line text-sm"></i>
                      </div>
                    </div>
                    {errors.title && <p className="text-xs text-red-500 mt-1">{errors.title}</p>}
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1.5">身份证号 <span className="text-red-500">*</span></label>
                    <div className="relative">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-id-card-line text-sm"></i>
                      </div>
                      <input
                        type="text"
                        name="idCardNo"
                        value={teacherForm.idCardNo}
                        onChange={e => updateTeacher('idCardNo', e.target.value)}
                        placeholder="请输入18位身份证号"
                        maxLength={18}
                        className={inputClass}
                      />
                    </div>
                    {errors.idCardNo && <p className="text-xs text-red-500 mt-1">{errors.idCardNo}</p>}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">资质证明 <span className="text-gray-400 font-normal">（选填）</span></label>
                  <div className="border-2 border-dashed border-orange-200 hover:border-orange-400 hover:bg-orange-50 rounded-lg p-4 text-center cursor-pointer transition-colors">
                    <div className="w-8 h-8 flex items-center justify-center mx-auto mb-2 text-gray-400">
                      <i className="ri-upload-cloud-2-line text-2xl"></i>
                    </div>
                    <p className="text-xs text-gray-500">上传教师资格证或在职证明</p>
                    <p className="text-xs text-gray-400 mt-0.5">支持 JPG、PNG、PDF，不超过 5MB</p>
                  </div>
                </div>

                <div className="rounded-lg border p-3 border-orange-200 bg-orange-50">
                  <div className="flex items-start gap-2">
                    <i className="ri-information-line text-sm mt-0.5 text-orange-500"></i>
                    <p className="text-xs text-gray-600 leading-relaxed">
                      教师注册需经管理员人工审核，核验工号与身份证信息，审核周期约1-3个工作日。
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* ===== Step 3: 账号安全 ===== */}
            {step === 3 && (
              <div className="space-y-4">
                {/* 邮箱验证码 */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">
                    邮箱验证码 <span className="text-gray-400 font-normal">（发送至 {currentEmail || '您的邮箱'}）</span>
                  </label>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                        <i className="ri-shield-keyhole-line text-sm"></i>
                      </div>
                      <input
                        type="text"
                        name="verifyCode"
                        value={role === 'student' ? studentForm.verifyCode : teacherForm.verifyCode}
                        onChange={e => role === 'student' ? updateStudent('verifyCode', e.target.value) : updateTeacher('verifyCode', e.target.value)}
                        placeholder="请输入6位验证码"
                        maxLength={6}
                        className={inputClass}
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleSendCode}
                      disabled={codeCountdown > 0}
                      className={`px-3 py-2.5 text-xs font-medium rounded-lg whitespace-nowrap transition-all cursor-pointer border ${
                        codeCountdown > 0
                          ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed'
                          : role === 'student'
                          ? 'bg-teal-50 text-teal-600 border-teal-200 hover:bg-teal-100'
                          : 'bg-orange-50 text-orange-600 border-orange-200 hover:bg-orange-100'
                      }`}
                    >
                      {codeCountdown > 0 ? `${codeCountdown}s后重发` : codeSent ? '重新发送' : '发送验证码'}
                    </button>
                  </div>
                  {codeSent && codeCountdown > 0 && (
                    <p className="text-xs text-gray-400 mt-1">验证码已发送至 {currentEmail}，请注意查收</p>
                  )}
                  {errors.verifyCode && <p className="text-xs text-red-500 mt-1">{errors.verifyCode}</p>}
                </div>

                {/* 设置密码 */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">设置密码 <span className="text-red-500">*</span></label>
                  <div className="relative">
                    <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                      <i className="ri-lock-line text-sm"></i>
                    </div>
                    <input
                      type={showPwd ? 'text' : 'password'}
                      name="password"
                      value={role === 'student' ? studentForm.password : teacherForm.password}
                      onChange={e => role === 'student' ? updateStudent('password', e.target.value) : updateTeacher('password', e.target.value)}
                      placeholder="至少8位，包含字母和数字"
                      className={`${inputClass} pr-10`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd(!showPwd)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                    >
                      <i className={`${showPwd ? 'ri-eye-off-line' : 'ri-eye-line'} text-sm`}></i>
                    </button>
                  </div>
                  {errors.password && <p className="text-xs text-red-500 mt-1">{errors.password}</p>}
                  {/* 密码强度条 */}
                  {(role === 'student' ? studentForm.password : teacherForm.password) && (() => {
                    const pwd = role === 'student' ? studentForm.password : teacherForm.password;
                    const strength = getPwdStrength(pwd);
                    return (
                      <div className="mt-2">
                        <div className="flex gap-1 mb-1">
                          {[1, 2, 3, 4].map(i => (
                            <div key={i} className={`flex-1 h-1 rounded-full transition-all ${i <= strength ? strengthColors[strength] : 'bg-gray-200'}`}></div>
                          ))}
                        </div>
                        <p className="text-xs text-gray-400">密码强度：<span className="font-medium">{strengthLabels[strength]}</span></p>
                      </div>
                    );
                  })()}
                </div>

                {/* 确认密码 */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1.5">确认密码 <span className="text-red-500">*</span></label>
                  <div className="relative">
                    <div className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400">
                      <i className="ri-lock-2-line text-sm"></i>
                    </div>
                    <input
                      type={showConfirmPwd ? 'text' : 'password'}
                      name="confirmPassword"
                      value={role === 'student' ? studentForm.confirmPassword : teacherForm.confirmPassword}
                      onChange={e => role === 'student' ? updateStudent('confirmPassword', e.target.value) : updateTeacher('confirmPassword', e.target.value)}
                      placeholder="请再次输入密码"
                      className={`${inputClass} pr-10`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPwd(!showConfirmPwd)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center text-gray-400 hover:text-gray-600 cursor-pointer"
                    >
                      <i className={`${showConfirmPwd ? 'ri-eye-off-line' : 'ri-eye-line'} text-sm`}></i>
                    </button>
                  </div>
                  {errors.confirmPassword && <p className="text-xs text-red-500 mt-1">{errors.confirmPassword}</p>}
                  {/* 密码一致提示 */}
                  {(role === 'student' ? studentForm.confirmPassword : teacherForm.confirmPassword) &&
                    (role === 'student' ? studentForm.password === studentForm.confirmPassword : teacherForm.password === teacherForm.confirmPassword) && (
                    <p className="text-xs text-green-500 mt-1 flex items-center gap-1">
                      <i className="ri-check-line"></i> 两次密码一致
                    </p>
                  )}
                </div>

                {/* 安全提示 */}
                <div className={`rounded-lg border p-3 ${borderAccentColor} ${bgAccent}`}>
                  <p className="text-xs font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
                    <i className={`ri-shield-check-line ${textAccent}`}></i>
                    密码安全建议
                  </p>
                  <ul className="text-xs text-gray-500 space-y-0.5 leading-relaxed">
                    <li className={`flex items-center gap-1.5 ${(role === 'student' ? studentForm.password.length : teacherForm.password.length) >= 8 ? 'text-green-600' : ''}`}>
                      <i className={`${(role === 'student' ? studentForm.password.length : teacherForm.password.length) >= 8 ? 'ri-check-line text-green-500' : 'ri-circle-line text-gray-300'} text-xs`}></i>
                      至少8个字符
                    </li>
                    <li className={`flex items-center gap-1.5 ${/[a-zA-Z]/.test(role === 'student' ? studentForm.password : teacherForm.password) ? 'text-green-600' : ''}`}>
                      <i className={`${/[a-zA-Z]/.test(role === 'student' ? studentForm.password : teacherForm.password) ? 'ri-check-line text-green-500' : 'ri-circle-line text-gray-300'} text-xs`}></i>
                      包含英文字母
                    </li>
                    <li className={`flex items-center gap-1.5 ${/\d/.test(role === 'student' ? studentForm.password : teacherForm.password) ? 'text-green-600' : ''}`}>
                      <i className={`${/\d/.test(role === 'student' ? studentForm.password : teacherForm.password) ? 'ri-check-line text-green-500' : 'ri-circle-line text-gray-300'} text-xs`}></i>
                      包含数字
                    </li>
                    <li className={`flex items-center gap-1.5 ${/[^a-zA-Z0-9]/.test(role === 'student' ? studentForm.password : teacherForm.password) ? 'text-green-600' : ''}`}>
                      <i className={`${/[^a-zA-Z0-9]/.test(role === 'student' ? studentForm.password : teacherForm.password) ? 'ri-check-line text-green-500' : 'ri-circle-line text-gray-300'} text-xs`}></i>
                      包含特殊字符（可选，更安全）
                    </li>
                  </ul>
                </div>

                {/* 用户协议 */}
                <div>
                  <label className="flex items-start gap-2.5 cursor-pointer">
                    <div className="relative mt-0.5 shrink-0">
                      <div
                        onClick={() => role === 'student' ? updateStudent('agree', !studentForm.agree) : updateTeacher('agree', !teacherForm.agree)}
                        className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-all cursor-pointer ${
                          (role === 'student' ? studentForm.agree : teacherForm.agree)
                            ? `${role === 'student' ? 'bg-teal-500 border-teal-500' : 'bg-orange-500 border-orange-500'}`
                            : 'border-gray-300 bg-white'
                        }`}
                      >
                        {(role === 'student' ? studentForm.agree : teacherForm.agree) && (
                          <i className="ri-check-line text-white text-xs"></i>
                        )}
                      </div>
                    </div>
                    <span className="text-xs text-gray-600 leading-relaxed">
                      我已阅读并同意
                      <a href="#" className={`${textAccent} hover:underline mx-0.5`}>《用户服务协议》</a>
                      和
                      <a href="#" className={`${textAccent} hover:underline mx-0.5`}>《隐私政策》</a>
                      ，并确认所填信息真实有效
                    </span>
                  </label>
                  {errors.agree && <p className="text-xs text-red-500 mt-1">{errors.agree}</p>}
                </div>

                {errors.submit && (
                  <div className="flex items-center gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg">
                    <i className="ri-error-warning-line text-red-500 text-sm"></i>
                    <span className="text-xs text-red-600">{errors.submit}</span>
                  </div>
                )}
              </div>
            )}

            {/* 按钮区 */}
            <div className="flex gap-3 mt-6">
              {step > 1 && (
                <button
                  type="button"
                  onClick={handleBack}
                  className="flex-1 py-2.5 text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-all cursor-pointer whitespace-nowrap"
                >
                  <span className="flex items-center justify-center gap-1.5">
                    <i className="ri-arrow-left-line text-sm"></i>
                    上一步
                  </span>
                </button>
              )}
              {step < 3 ? (
                <button
                  type="button"
                  onClick={handleNext}
                  className={`flex-1 py-2.5 text-sm font-semibold text-white rounded-lg transition-all cursor-pointer whitespace-nowrap ${btnClass}`}
                >
                  <span className="flex items-center justify-center gap-1.5">
                    下一步
                    <i className="ri-arrow-right-line text-sm"></i>
                  </span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={loading}
                  className={`flex-1 py-2.5 text-sm font-semibold text-white rounded-lg transition-all cursor-pointer whitespace-nowrap ${loading ? 'opacity-70 cursor-not-allowed' : ''} ${btnClass}`}
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <i className="ri-loader-4-line animate-spin text-sm"></i>
                      提交中...
                    </span>
                  ) : (
                    <span className="flex items-center justify-center gap-1.5">
                      <i className="ri-send-plane-line text-sm"></i>
                      提交注册申请
                    </span>
                  )}
                </button>
              )}
            </div>
          </form>

          <p className="text-center text-xs text-gray-400 mt-5">
            已有账号？
            <button type="button" onClick={() => navigate('/login')} className={`${textAccent} font-medium ml-1 cursor-pointer whitespace-nowrap hover:underline`}>立即登录</button>
          </p>
          <p className="text-center text-xs text-gray-300 mt-3">
            © 2025 珞樱学堂 · 武汉大学智能教育实验室
          </p>
        </div>
      </div>
    </div>
  );
}
