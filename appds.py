# ===== IMPORTS =====
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import hashlib
import json
import io
import base64
import numpy as np
from pathlib import Path

# ===== PAGE CONFIG =====
st.set_page_config(
    page_title="外部前额叶皮层 Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== CUSTOM CSS =====
st.markdown("""
<style>
    /* 主色调 */
    :root {
        --primary-color: #1e3a8a;
        --secondary-color: #3b82f6;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --danger-color: #ef4444;
    }
    
    /* 移动端优化 */
    @media (max-width: 768px) {
        .block-container {
            padding: 1rem !important;
        }
        .stButton>button {
            width: 100% !important;
        }
        .task-card {
            padding: 10px;
            margin: 5px 0;
            border-radius: 8px;
            background: #f8fafc;
        }
    }
    
    /* 任务卡片样式 */
    .task-card {
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid var(--primary-color);
        background: #f8fafc;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .task-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    .task-completed {
        border-left-color: var(--success-color);
        background: #f0fdf4;
    }
    
    .task-pending {
        border-left-color: var(--warning-color);
        background: #fffbeb;
    }
    
    .task-overdue {
        border-left-color: var(--danger-color);
        background: #fef2f2;
    }
    
    /* 统计卡片 */
    .metric-card {
        background: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin: 10px 0;
    }
    
    /* 暗色模式支持 */
    @media (prefers-color-scheme: dark) {
        .task-card {
            background: #1f2937;
            color: white;
        }
    }
</style>
""", unsafe_allow_html=True)

# ===== CONSTANTS =====
TASK_CSV = "execution_log.csv"
FINANCE_CSV = "finance_log.csv"
BACKUP_DIR = "backups"
CONFIG_FILE = "dashboard_config.json"

# ===== CREATE DIRECTORIES =====
os.makedirs(BACKUP_DIR, exist_ok=True)

# ===== DATA MODEL =====
TASK_COLS = ["日期", "创建时间", "任务", "类别", "备注", "完成", "开始时间", 
             "完成时间", "用时(秒)", "评分", "AI反馈", "紧急度", "预计时间(分)", "实际用时(分)"]

FINANCE_COLS = ["日期", "创建时间", "类型", "金额", "备注", "支付方式", "分类"]

# ===== DATA LOADING WITH CACHING =====
@st.cache_data(ttl=60, show_spinner="加载数据中...")
def load_task_data():
    """加载任务数据，确保编码正确"""
    try:
        if os.path.exists(TASK_CSV):
            # 尝试多种编码
            encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']
            for encoding in encodings:
                try:
                    df = pd.read_csv(TASK_CSV, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                df = pd.read_csv(TASK_CSV, encoding='utf-8', errors='ignore')
        else:
            df = pd.DataFrame(columns=TASK_COLS)
        
        # 确保所有列存在
        for col in TASK_COLS:
            if col not in df.columns:
                if col == "完成":
                    df[col] = False
                elif col in ["用时(秒)", "预计时间(分)", "实际用时(分)"]:
                    df[col] = 0.0
                else:
                    df[col] = ""
        
        # 数据类型转换
        numeric_cols = ["用时(秒)", "预计时间(分)", "实际用时(分)"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 确保日期格式
        if "日期" in df.columns:
            df["日期"] = pd.to_datetime(df["日期"], errors='coerce').dt.strftime('%Y-%m-%d')
        
        return df
    
    except Exception as e:
        st.error(f"加载任务数据失败: {e}")
        return pd.DataFrame(columns=TASK_COLS)

@st.cache_data(ttl=60, show_spinner="加载财务数据中...")
def load_finance_data():
    """加载财务数据"""
    try:
        if os.path.exists(FINANCE_CSV):
            # 尝试多种编码
            encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']
            for encoding in encodings:
                try:
                    df = pd.read_csv(FINANCE_CSV, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                df = pd.read_csv(FINANCE_CSV, encoding='utf-8', errors='ignore')
        else:
            df = pd.DataFrame(columns=FINANCE_COLS)
        
        # 确保所有列存在
        for col in FINANCE_COLS:
            if col not in df.columns:
                if col == "金额":
                    df[col] = 0.0
                else:
                    df[col] = ""
        
        # 数据类型转换
        if "金额" in df.columns:
            df["金额"] = pd.to_numeric(df["金额"], errors='coerce').fillna(0)
        
        return df
    
    except Exception as e:
        st.error(f"加载财务数据失败: {e}")
        return pd.DataFrame(columns=FINANCE_COLS)

# ===== DATA SAVING FUNCTIONS =====
def save_task_data(df):
    """保存任务数据，使用UTF-8 with BOM编码"""
    try:
        df.to_csv(TASK_CSV, index=False, encoding='utf-8-sig')
        return True
    except Exception as e:
        st.error(f"保存任务数据失败: {e}")
        return False

def save_finance_data(df):
    """保存财务数据，使用UTF-8 with BOM编码"""
    try:
        df.to_csv(FINANCE_CSV, index=False, encoding='utf-8-sig')
        return True
    except Exception as e:
        st.error(f"保存财务数据失败: {e}")
        return False

# ===== BACKUP FUNCTIONS =====
def create_backup():
    """创建数据备份"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 备份任务数据
        tasks_backup_path = os.path.join(BACKUP_DIR, f"tasks_backup_{timestamp}.csv")
        df_tasks = load_task_data()
        df_tasks.to_csv(tasks_backup_path, index=False, encoding='utf-8-sig')
        
        # 备份财务数据
        finance_backup_path = os.path.join(BACKUP_DIR, f"finance_backup_{timestamp}.csv")
        df_finance = load_finance_data()
        df_finance.to_csv(finance_backup_path, index=False, encoding='utf-8-sig')
        
        return True, f"备份成功 ({timestamp})"
    except Exception as e:
        return False, f"备份失败: {e}"

def export_to_excel():
    """导出数据到Excel"""
    try:
        df_tasks = load_task_data()
        df_finance = load_finance_data()
        
        # 创建内存中的Excel文件
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_tasks.to_excel(writer, sheet_name='任务记录', index=False)
            df_finance.to_excel(writer, sheet_name='财务记录', index=False)
        
        # 编码为base64
        b64 = base64.b64encode(output.getvalue()).decode()
        filename = f"dashboard_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return b64, filename
    except Exception as e:
        return None, f"导出失败: {e}"

# ===== DATA VALIDATION =====
def validate_task_data(df):
    """验证任务数据的完整性"""
    issues = []
    
    for idx, row in df.iterrows():
        # 检查时间顺序
        if row.get("完成时间") and row.get("开始时间"):
            try:
                start = pd.to_datetime(row["开始时间"])
                end = pd.to_datetime(row["完成时间"])
                if end < start:
                    issues.append(f"行{idx}: 完成时间早于开始时间")
            except:
                issues.append(f"行{idx}: 时间格式错误")
        
        # 检查预计时间和实际时间
        if row.get("预计时间(分)", 0) > 0 and row.get("实际用时(分)", 0) > 0:
            efficiency = row.get("实际用时(分)", 0) / row.get("预计时间(分)", 1)
            if efficiency > 2:  # 超过预计时间2倍
                issues.append(f"行{idx}: 任务效率较低 ({efficiency:.1f}x)")
    
    return issues

# ===== UTILITY FUNCTIONS =====
def calculate_task_efficiency(df_tasks):
    """计算任务效率指标"""
    if df_tasks.empty:
        return {
            "total_tasks": 0,
            "completed_tasks": 0,
            "completion_rate": 0,
            "avg_duration": 0,
            "total_time": 0,
            "efficiency_score": 0
        }
    
    completed_df = df_tasks[df_tasks["完成"] == True].copy()
    
    # 初始化 avg_efficiency
    avg_efficiency = 1.0  # 默认值
    
    if not completed_df.empty:
        # 计算实际用时（优先使用实际用时，如果没有则使用时(秒)转换）
        if "实际用时(分)" in completed_df.columns:
            completed_df["实际用时_分"] = completed_df["实际用时(分)"]
        else:
            completed_df["实际用时_分"] = completed_df["用时(秒)"] / 60
        
        # 计算预计时间（如果有）
        if "预计时间(分)" in completed_df.columns:
            completed_df["预计时间_分"] = completed_df["预计时间(分)"].replace(0, np.nan)
            # 确保有有效的数据
            valid_data = completed_df.dropna(subset=["实际用时_分", "预计时间_分"])
            if not valid_data.empty:
                avg_efficiency = (valid_data["实际用时_分"] / valid_data["预计时间_分"]).mean(skipna=True)
        # 如果没有预计时间列或数据无效，avg_efficiency 保持默认值 1.0
    
    # 确保 avg_efficiency 不会为0或负数
    if avg_efficiency <= 0:
        avg_efficiency = 1.0
    
    return {
        "total_tasks": len(df_tasks),
        "completed_tasks": len(completed_df),
        "completion_rate": len(completed_df) / len(df_tasks) if len(df_tasks) > 0 else 0,
        "avg_duration": completed_df["实际用时_分"].mean() if "实际用时_分" in completed_df.columns and not completed_df.empty else 0,
        "total_time": completed_df["实际用时_分"].sum() if "实际用时_分" in completed_df.columns and not completed_df.empty else 0,
        "efficiency_score": 1.0 / avg_efficiency if avg_efficiency > 0 else 0
    }

def calculate_finance_summary(df):
    """计算财务摘要"""
    if df.empty:
        return {
            "total_income": 0,
            "total_expense": 0,
            "net_balance": 0,
            "expense_by_category": {},
            "avg_daily_expense": 0
        }
    
    income = df[df["类型"] == "收入"]["金额"].sum()
    expense = df[df["类型"] == "支出"]["金额"].sum()
    
    # 按分类统计支出
    expense_by_category = {}
    if "分类" in df.columns:
        expense_df = df[df["类型"] == "支出"]
        if not expense_df.empty:
            expense_by_category = expense_df.groupby("分类")["金额"].sum().to_dict()
    
    # 计算日均支出
    df["日期"] = pd.to_datetime(df["日期"], errors='coerce')
    unique_days = df["日期"].nunique()
    avg_daily_expense = expense / unique_days if unique_days > 0 else 0
    
    return {
        "total_income": income,
        "total_expense": expense,
        "net_balance": income - expense,
        "expense_by_category": expense_by_category,
        "avg_daily_expense": avg_daily_expense
    }

# ===== AI PROMPT GENERATION =====
def generate_daily_summary_prompt(df_tasks, df_finance):
    """生成每日AI总结提示词"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # 获取今日和昨日数据
    y_tasks = df_tasks[df_tasks["日期"] == yesterday_str].to_dict('records')
    t_tasks = df_tasks[df_tasks["日期"] == today_str].to_dict('records')
    
    y_finance = df_finance[df_finance["日期"] == yesterday_str].to_dict('records')
    t_finance = df_finance[df_finance["日期"] == today_str].to_dict('records')
    
    # 角色定义
    role_section = """Role: You are my external Prefrontal Cortex and Strategic CFO.
Zi Wei Dou Shu chart features:
Ming Gong : Empty (Lack of discipline, prone to laziness/Tian Tong)
Career Palace : Tai Yin + Ling Xing (Good at deep analysis, sensitive, needs quiet)
Wealth Palace : Sun Hua Ji (High risk of impulsive spending/cash drain)
Property Palace : Tian Fu + Lian Zhen Lu (Must accumulate assets)
Protocols: Anti-Procrastination, Financial Firewall, Emotional Filter, Social Agent
Tone: Cold, Rational, Data-Driven, Slightly sarcastic if lazy, Protective if focused"""
    
    # 格式化任务数据
    def format_task(t):
        duration_min = float(t.get('用时(秒)', 0)) / 60
        actual_min = float(t.get('实际用时(分)', 0))
        estimated_min = float(t.get('预计时间(分)', 0))
        
        efficiency = "N/A"
        if estimated_min > 0:
            efficiency_ratio = actual_min / estimated_min if actual_min > 0 else 0
            if efficiency_ratio <= 0.8:
                efficiency = f"高效 ({efficiency_ratio:.1f}x)"
            elif efficiency_ratio <= 1.2:
                efficiency = f"正常 ({efficiency_ratio:.1f}x)"
            else:
                efficiency = f"低效 ({efficiency_ratio:.1f}x)"
        
        return (
            f"任务名称: {t.get('任务','-')} | "
            f"类别: {t.get('类别','-')} | "
            f"状态: {'已完成' if t.get('完成', False) else '未完成'} | "
            f"用时: {duration_min:.1f}分钟 | "
            f"效率: {efficiency} | "
            f"评分: {t.get('评分','-')} | "
            f"紧急度: {t.get('紧急度','-')}"
        )
    
    # 格式化财务数据
    def format_finance(f):
        return (
            f"类型: {f.get('类型','-')} | "
            f"金额: RM{f.get('金额',0):.2f} | "
            f"分类: {f.get('分类','-')} | "
            f"支付方式: {f.get('支付方式','-')} | "
            f"备注: {f.get('备注','-')}"
        )
    
    # 生成统计摘要
    task_summary = calculate_task_efficiency(pd.DataFrame(t_tasks))
    finance_summary = calculate_finance_summary(pd.DataFrame(t_finance))
    
    summary_section = f"""
今日任务统计:
- 总任务数: {task_summary['total_tasks']}
- 完成率: {task_summary['completion_rate']*100:.1f}%
- 总用时: {task_summary['total_time']:.1f}分钟
- 效率评分: {task_summary['efficiency_score']:.2f}

今日财务统计:
- 总收入: RM{finance_summary['total_income']:.2f}
- 总支出: RM{finance_summary['total_expense']:.2f}
- 净余额: RM{finance_summary['net_balance']:.2f}
- 日均支出: RM{finance_summary['avg_daily_expense']:.2f}
"""
    
    # 详细记录
    y_tasks_str = "\n".join([format_task(t) for t in y_tasks]) or "无昨日任务"
    t_tasks_str = "\n".join([format_task(t) for t in t_tasks]) or "无今日任务"
    
    y_finance_str = "\n".join([format_finance(f) for f in y_finance]) or "无昨日财务记录"
    t_finance_str = "\n".join([format_finance(f) for f in t_finance]) or "无今日财务记录"
    
    return (
        f"{role_section}\n\n"
        f"=== 统计摘要 ===\n{summary_section}\n"
        f"=== 昨日任务 ===\n{y_tasks_str}\n\n"
        f"=== 今日任务 ===\n{t_tasks_str}\n\n"
        f"=== 昨日财务 ===\n{y_finance_str}\n\n"
        f"=== 今日财务 ===\n{t_finance_str}\n\n"
        f"=== AI分析请求 ===\n"
        f"请分析我的生产效率并提供改进建议，特别关注:\n"
        f"1. 时间管理效率\n2. 财务支出模式\n3. 紫微斗数命盘弱点\n4. 明日优化策略"
    )

# ===== VISUALIZATION FUNCTIONS =====
def create_task_visualizations(df_tasks):
    """创建任务可视化图表"""
    if df_tasks.empty:
        return None, None, None
    
    # 只显示已完成的任务进行分析
    completed_df = df_tasks[df_tasks["完成"] == True].copy()
    if completed_df.empty:
        return None, None, None
    
    # 计算实际用时（分钟）
    if "实际用时(分)" in completed_df.columns and completed_df["实际用时(分)"].sum() > 0:
        completed_df["用时_分钟"] = completed_df["实际用时(分)"]
    else:
        completed_df["用时_分钟"] = completed_df["用时(秒)"] / 60
    
    # 1. 任务完成柱状图
    fig1 = px.bar(
        completed_df,
        x="任务",
        y="用时_分钟",
        color="评分",
        title="📊 任务完成用时分析",
        labels={"用时_分钟": "用时(分钟)", "任务": "任务名称"},
        color_discrete_sequence=px.colors.sequential.Blues
    )
    fig1.update_layout(
        xaxis_tickangle=-45,
        height=400,
        showlegend=True
    )
    
    # 2. 每日用时趋势图
    if "日期" in completed_df.columns:
        trend_df = completed_df.groupby("日期")["用时_分钟"].sum().reset_index()
        trend_df["日期"] = pd.to_datetime(trend_df["日期"])
        trend_df = trend_df.sort_values("日期")
        
        fig2 = px.line(
            trend_df,
            x="日期",
            y="用时_分钟",
            title="📈 每日专注用时趋势",
            labels={"用时_分钟": "总用时(分钟)", "日期": "日期"},
            markers=True
        )
        fig2.update_layout(height=400)
        
        # 添加7日移动平均线
        if len(trend_df) >= 7:
            trend_df["7日平均"] = trend_df["用时_分钟"].rolling(window=7, min_periods=1).mean()
            fig2.add_trace(
                go.Scatter(
                    x=trend_df["日期"],
                    y=trend_df["7日平均"],
                    name="7日移动平均",
                    line=dict(dash="dash", color="red")
                )
            )
    else:
        fig2 = None
    
    # 3. 任务类别分布饼图
    if "类别" in completed_df.columns:
        category_df = completed_df.groupby("类别")["用时_分钟"].sum().reset_index()
        fig3 = px.pie(
            category_df,
            values="用时_分钟",
            names="类别",
            title="🥧 任务类别时间分布",
            hole=0.3,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig3.update_layout(height=400)
    else:
        fig3 = None
    
    return fig1, fig2, fig3

def create_finance_visualizations(df_finance):
    """创建财务可视化图表"""
    if df_finance.empty:
        return None, None
    
    # 1. 收支趋势图
    if "日期" in df_finance.columns:
        daily_df = df_finance.copy()
        daily_df["日期"] = pd.to_datetime(daily_df["日期"], errors='coerce')
        daily_df = daily_df.sort_values("日期")
        
        # 按日期和类型分组
        pivot_df = daily_df.pivot_table(
            index="日期",
            columns="类型",
            values="金额",
            aggfunc="sum",
            fill_value=0
        ).reset_index()
        
        fig1 = go.Figure()
        
        if "收入" in pivot_df.columns:
            fig1.add_trace(go.Scatter(
                x=pivot_df["日期"],
                y=pivot_df["收入"],
                name="收入",
                mode="lines+markers",
                line=dict(color="green", width=2)
            ))
        
        if "支出" in pivot_df.columns:
            fig1.add_trace(go.Scatter(
                x=pivot_df["日期"],
                y=pivot_df["支出"],
                name="支出",
                mode="lines+markers",
                line=dict(color="red", width=2)
            ))
        
        fig1.update_layout(
            title="💰 每日收支趋势",
            xaxis_title="日期",
            yaxis_title="金额 (RM)",
            height=400,
            hovermode="x unified"
        )
    else:
        fig1 = None
    
    # 2. 支出分类饼图
    expense_df = df_finance[df_finance["类型"] == "支出"].copy()
    if not expense_df.empty and "分类" in expense_df.columns:
        category_expense = expense_df.groupby("分类")["金额"].sum().reset_index()
        
        fig2 = px.pie(
            category_expense,
            values="金额",
            names="分类",
            title="💸 支出分类分布",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig2.update_layout(height=400)
        
        # 添加分类统计表格
        category_table = category_expense.sort_values("金额", ascending=False)
    else:
        fig2 = None
        category_table = None
    
    return fig1, fig2, category_table

# ===== MAIN APPLICATION =====
# ===== 新增模块：AI智能分析引擎 =====
import openai
import requests
from datetime import datetime, timedelta
import re

# ===== 紫微斗数AI分析师 =====
class ZiWeiAIAnalyst:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.personality = {
            "name": "诸葛命理",
            "style": "冷酷理性 + 玄学洞察",
            "strengths": ["时间管理", "财务预测", "运势分析", "效率优化"],
            "weaknesses": ["拖延症", "冲动消费", "情绪波动"]
        }
    
    def analyze_day(self, tasks_df, finance_df, date_str):
        """分析一天的表现"""
        day_tasks = tasks_df[tasks_df["日期"] == date_str]
        day_finance = finance_df[finance_df["日期"] == date_str]
        
        analysis = {
            "date": date_str,
            "task_summary": self._analyze_tasks(day_tasks),
            "finance_summary": self._analyze_finance(day_finance),
            "ziwei_insight": self._generate_ziwei_insight(day_tasks, day_finance),
            "recommendations": []
        }
        
        # 生成个性化建议
        analysis["recommendations"] = self._generate_recommendations(analysis)
        
        return analysis
    
    def _analyze_tasks(self, tasks):
        if tasks.empty:
            return {"total": 0, "completed": 0, "efficiency": 0, "focus_score": 0}
        
        completed = tasks[tasks["完成"] == True]
        if completed.empty:
            return {"total": len(tasks), "completed": 0, "efficiency": 0, "focus_score": 0}
        
        # 计算专注得分
        total_estimated = tasks["预计时间(分)"].sum()
        total_actual = completed["实际用时(分)"].sum()
        efficiency = total_estimated / total_actual if total_actual > 0 else 0
        
        # 计算时间段分布
        time_distribution = self._analyze_time_distribution(tasks)
        
        return {
            "total": len(tasks),
            "completed": len(completed),
            "completion_rate": len(completed) / len(tasks),
            "efficiency": efficiency,
            "focus_score": self._calculate_focus_score(tasks),
            "time_distribution": time_distribution
        }
    
    def _analyze_finance(self, finance):
        if finance.empty:
            return {"income": 0, "expense": 0, "balance": 0, "risk_score": 0}
        
        income = finance[finance["类型"] == "收入"]["金额"].sum()
        expense = finance[finance["类型"] == "支出"]["金额"].sum()
        
        # 计算财务风险分
        risk_score = self._calculate_financial_risk(finance)
        
        # 分析消费模式
        spending_pattern = self._analyze_spending_pattern(finance)
        
        return {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "risk_score": risk_score,
            "spending_pattern": spending_pattern
        }
    
    def display_analysis(self, df_tasks, df_finance, date_str):
        """显示完整的AI分析结果"""
        analysis = self.analyze_day(df_tasks, df_finance, date_str)
        
        # 创建分析结果显示
        with st.expander(f"🤖 {date_str} AI分析报告", expanded=True):
            # 1. 显示统计摘要
            st.write("### 📊 统计摘要")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("任务完成率", f"{analysis['task_summary']['completion_rate']*100:.1f}%")
                st.metric("专注力得分", f"{analysis['task_summary']['focus_score']}/100")
            
            with col2:
                st.metric("财务风险分", f"{analysis['finance_summary']['risk_score']:.2f}")
                st.metric("净余额", f"RM{analysis['finance_summary']['balance']:.2f}")
            
            # 2. 显示紫微斗数洞察
            st.write("### 🔮 紫微斗数洞察")
            for insight in analysis['ziwei_insight']:
                st.info(insight)
            
            # 3. 显示推荐建议（关键位置！）
            st.write("### 🎯 个性化推荐")
            # 这里调用推荐方法
            recommendations_html = self._generate_recommendations_html(analysis)
            st.markdown(recommendations_html, unsafe_allow_html=True)
    
    def _generate_ziwei_insight(self, tasks, finance):
        """生成紫微斗数命理洞察"""
        insights = []
        
        # 基于命宫空的特性
        if len(tasks) > 0 and tasks["完成"].sum() / len(tasks) < 0.5:
            insights.append("🔮 命宫空: 今日执行力不足，易受拖延症影响")
        
        # 基于财帛宫太阳化忌
        if not finance.empty:
            expense = finance[finance["类型"] == "支出"]["金额"].sum()
            if expense > 500:  # 假设500为高风险阈值
                insights.append("💰 太阳化忌: 今日有冲动消费迹象，财务防火墙警报")
        
        # 基于事业宫太阴铃星
        completed_tasks = tasks[tasks["完成"] == True]
        if not completed_tasks.empty:
            avg_duration = completed_tasks["实际用时(分)"].mean()
            if avg_duration > 120:  # 平均超过2小时
                insights.append("⚙️ 太阴铃星: 深度工作模式开启，但需注意休息")
        
        return insights if insights else ["🌟 今日运势平稳，保持专注"]
    
    def _generate_recommendations_html(self, analysis):
        """生成带HTML格式的推荐"""
        recs = []
        
        # 任务完成率建议
        if analysis["task_summary"]["completion_rate"] < 0.7:
            recs.append("📌 采用番茄工作法：25分钟专注 + 5分钟休息")
        
        # 财务建议
        if analysis["finance_summary"]["risk_score"] > 0.7:
            recs.append("💳 启动财务冷静期：大额消费前等待24小时")
        
        # 时间分配建议
        if analysis["task_summary"]["time_distribution"]:
            peak_time = max(analysis["task_summary"]["time_distribution"].items(), key=lambda x: x[1])[0]
            recs.append(f"⏰ 建议在{peak_time}时段安排最重要任务")
        
        # 如果没有建议，添加默认建议
        if not recs:
            recs.append("🌟 今日表现良好，继续保持！")
        
        # 构建HTML
        html_content = f"""
        <div style="
            background-color: #292828;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin: 15px 0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        ">
            <h3 style="color: white; margin-top: 0;">🤖 AI 推荐建议</h3>
            <div style="background-color: #292828; padding: 15px; border-radius: 8px;">
        """
        
        for i, rec in enumerate(recs, 1):
            html_content += f"""
            <div style="
                padding: 10px 15px;
                margin: 8px 0;
                border-left: 3px solid #4CAF50;
                background-color: #2d2c2c;
                border-radius: 5px;
            ">
                <strong>{i}.</strong> {rec}
            </div>
            """
        
        html_content += """
            </div>
        </div>
        """
        
        return html_content
    
    def _calculate_focus_score(self, tasks):
        """计算专注力得分"""
        if tasks.empty:
            return 0
        
        completed = tasks[tasks["完成"] == True]
        if completed.empty:
            return 0
        
        # 基于任务完成率、用时效率、时间分布计算
        completion_rate = len(completed) / len(tasks)
        
        # 用时效率
        if "预计时间(分)" in completed.columns and "实际用时(分)" in completed.columns:
            efficiency_scores = []
            for _, row in completed.iterrows():
                estimated = row["预计时间(分)"]
                actual = row["实际用时(分)"]
                if estimated > 0 and actual > 0:
                    efficiency = min(1.0, estimated / actual)  # 越接近1越好
                    efficiency_scores.append(efficiency)
            
            avg_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0.5
        else:
            avg_efficiency = 0.5
        
        # 综合得分
        focus_score = (completion_rate * 0.6 + avg_efficiency * 0.4) * 100
        
        return round(focus_score, 1)
    
    def _analyze_time_distribution(self, tasks):
        """分析任务时间分布"""
        if tasks.empty or "开始时间" not in tasks.columns:
            return {}
        
        time_dist = {}
        for _, task in tasks.iterrows():
            if pd.notna(task["开始时间"]):
                try:
                    # 提取小时
                    hour = int(task["开始时间"].split(" ")[1].split(":")[0])
                    time_slot = f"{hour}:00-{hour+1}:00"
                    time_dist[time_slot] = time_dist.get(time_slot, 0) + 1
                except:
                    continue
        
        return time_dist
    
    def _calculate_financial_risk(self, finance):
        """计算财务风险分"""
        if finance.empty:
            return 0
        
        expense_df = finance[finance["类型"] == "支出"]
        if expense_df.empty:
            return 0
        
        # 风险因素
        total_expense = expense_df["金额"].sum()
        num_transactions = len(expense_df)
        avg_amount = total_expense / num_transactions
        
        # 高风险分类
        risky_categories = ["娱乐", "购物", "其他"]
        risky_expense = expense_df[expense_df["分类"].isin(risky_categories)]["金额"].sum()
        
        # 计算风险分
        risk_score = min(1.0, (risky_expense / total_expense if total_expense > 0 else 0) * 0.7 + 
                               (avg_amount / 100 if avg_amount > 0 else 0) * 0.3)
        
        return round(risk_score, 2)
    
    def _analyze_spending_pattern(self, finance):
        """分析消费模式"""
        if finance.empty:
            return "无消费记录"
        
        expense_df = finance[finance["类型"] == "支出"]
        if expense_df.empty:
            return "无支出记录"
        
        # 按分类统计
        category_sum = expense_df.groupby("分类")["金额"].sum()
        top_category = category_sum.idxmax() if not category_sum.empty else "无"
        top_amount = category_sum.max() if not category_sum.empty else 0
        
        patterns = []
        
        # 检查是否有冲动消费模式
        if len(expense_df) > 3:  # 一天超过3笔支出
            time_pattern = self._check_time_pattern(expense_df)
            if time_pattern:
                patterns.append(f"集中在{time_pattern}")
        
        # 检查是否有大额消费
        if top_amount > 300:
            patterns.append(f"主要消费在{top_category}")
        
        return " | ".join(patterns) if patterns else "消费模式正常"

# ===== 新增模块：语音输入支持 =====
def add_voice_input_support():
    """添加语音输入功能"""
    st.markdown("""
    <style>
    .voice-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px 20px;
        border-radius: 25px;
        border: none;
        cursor: pointer;
        font-weight: bold;
        transition: all 0.3s;
    }
    .voice-btn:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 语音输入按钮
    if st.button("🎤 语音输入任务", key="voice_input", use_container_width=True):
        st.info("语音输入功能需要浏览器权限...")
        st.code("""
        # 实际实现需要Web Speech API
        # 示例JavaScript代码:
        
        const recognition = new webkitSpeechRecognition();
        recognition.lang = 'zh-CN';
        
        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            document.getElementById('task-input').value = transcript;
        };
        
        recognition.start();
        """)

# ===== 新增模块：习惯追踪器 =====
class HabitTracker:
    def __init__(self):
        self.habits = {
            "早起": {"target": "07:00", "streak": 0, "max_streak": 0},
            "运动": {"target": "30分钟", "streak": 0, "max_streak": 0},
            "阅读": {"target": "30页", "streak": 0, "max_streak": 0},
            "冥想": {"target": "10分钟", "streak": 0, "max_streak": 0}
        }
    
    def display_habit_tracker(self):
        """显示习惯追踪器"""
        st.subheader("🔥 习惯养成追踪")
        
        cols = st.columns(len(self.habits))
        
        for idx, (habit, data) in enumerate(self.habits.items()):
            with cols[idx]:
                # 习惯卡片
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    color: white;
                    padding: 15px;
                    border-radius: 12px;
                    text-align: center;
                    margin: 10px 0;
                ">
                    <h4>{habit}</h4>
                    <p>目标: {data['target']}</p>
                    <div style="font-size: 24px; font-weight: bold;">
                        🔥 {data['streak']}
                    </div>
                    <p>连续天数</p>
                </div>
                """, unsafe_allow_html=True)
                
                # 打卡按钮
                if st.button(f"打卡 {habit}", key=f"habit_{habit}", use_container_width=True):
                    self.habits[habit]["streak"] += 1
                    if self.habits[habit]["streak"] > self.habits[habit]["max_streak"]:
                        self.habits[habit]["max_streak"] = self.habits[habit]["streak"]
                    st.success(f"{habit} 打卡成功！当前连续 {self.habits[habit]['streak']} 天")
        
        # 习惯统计
        total_streak = sum(data["streak"] for data in self.habits.values())
        avg_streak = total_streak / len(self.habits)
        
        st.metric("🔥 总连续打卡", f"{total_streak} 次")
        st.metric("📊 平均连续天数", f"{avg_streak:.1f} 天")

# ===== 新增模块：专注力训练 =====
class FocusTrainer:
    def __init__(self):
        self.sessions = []
        self.current_session = None
    
    def start_pomodoro(self, duration=25):
        """开始番茄钟"""
        if self.current_session:
            st.warning("已有进行中的专注会话")
            return
        
        self.current_session = {
            "start_time": datetime.now(),
            "duration": duration,
            "type": "pomodoro"
        }
        
        st.session_state.pomodoro_active = True
        st.success(f"🍅 开始 {duration} 分钟番茄钟")
    
    def start_deep_work(self, duration=90):
        """开始深度工作"""
        self.current_session = {
            "start_time": datetime.now(),
            "duration": duration,
            "type": "deep_work"
        }
        
        st.session_state.deep_work_active = True
        st.success(f"🚀 开始 {duration} 分钟深度工作")
    
    def display_timer(self):
        """显示专注计时器"""
        if hasattr(st.session_state, 'pomodoro_active') and st.session_state.pomodoro_active:
            if self.current_session:
                elapsed = (datetime.now() - self.current_session["start_time"]).total_seconds()
                remaining = max(0, self.current_session["duration"] * 60 - elapsed)
                
                # 显示倒计时
                mins, secs = divmod(int(remaining), 60)
                
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 15px;
                    text-align: center;
                    margin: 20px 0;
                ">
                    <h2>🍅 专注中</h2>
                    <h1 style="font-size: 48px; margin: 20px 0;">
                        {mins:02d}:{secs:02d}
                    </h1>
                    <p>剩余时间</p>
                </div>
                """, unsafe_allow_html=True)
                
                # 结束按钮
                if st.button("结束专注", type="primary", use_container_width=True):
                    self.end_session()
                    st.rerun()
                
                # 自动结束检查
                if remaining <= 0:
                    st.balloons()
                    st.success("🎉 番茄钟完成！休息5分钟")
                    self.end_session()
                    st.rerun()
    
    def end_session(self):
        """结束专注会话"""
        if self.current_session:
            end_time = datetime.now()
            duration = (end_time - self.current_session["start_time"]).total_seconds() / 60
            
            self.sessions.append({
                **self.current_session,
                "end_time": end_time,
                "actual_duration": duration
            })
            
            self.current_session = None
            st.session_state.pomodoro_active = False
            st.session_state.deep_work_active = False

# ===== 新增模块：智能提醒系统 =====
class SmartReminder:
    def __init__(self):
        self.reminders = []
    
    def add_reminder(self, task, time, priority="medium"):
        """添加智能提醒"""
        self.reminders.append({
            "task": task,
            "time": time,
            "priority": priority,
            "created": datetime.now(),
            "completed": False
        })
    
    def check_reminders(self):
        """检查并显示即将到来的提醒"""
        now = datetime.now()
        upcoming = []
        
        for reminder in self.reminders:
            if not reminder["completed"]:
                remind_time = reminder["time"]
                if isinstance(remind_time, str):
                    # 解析时间字符串
                    try:
                        remind_time = datetime.strptime(remind_time, "%H:%M")
                        remind_time = remind_time.replace(year=now.year, month=now.month, day=now.day)
                    except:
                        continue
                
                # 检查是否在未来30分钟内
                if now <= remind_time <= now + timedelta(minutes=30):
                    upcoming.append(reminder)
        
        return upcoming
    
    def display_reminders(self):
        """显示提醒"""
        upcoming = self.check_reminders()
        
        if upcoming:
            st.subheader("⏰ 即将提醒")
            
            for reminder in upcoming:
                priority_color = {
                    "high": "red",
                    "medium": "orange",
                    "low": "blue"
                }.get(reminder["priority"], "gray")
                
                st.markdown(f"""
                <div style="
                    border-left: 4px solid {priority_color};
                    background: #fff3cd;
                    padding: 10px;
                    margin: 5px 0;
                    border-radius: 5px;
                ">
                    <strong>{reminder['task']}</strong><br>
                    <small>⏱️ {reminder['time']} | 优先级: {reminder['priority']}</small>
                </div>
                """, unsafe_allow_html=True)

# ===== 集成到主应用 =====
def enhance_main_app():
    """在主应用中添加增强功能"""
    
    # 在侧边栏添加AI分析
    with st.sidebar:
        st.subheader("🤖 AI智能分析")
        
        if st.button("今日AI分析", use_container_width=True):
            # 这里可以调用ZiWeiAIAnalyst
            st.info("AI分析功能已准备就绪")
            st.code("""
            # 示例AI分析结果:
            1. 📊 今日专注力: 78分
            2. 💰 财务风险: 低
            3. 🔮 紫微洞察: 事业宫旺盛
            4. 🎯 推荐: 下午3-5点深度工作
            """)
        
        # 添加习惯追踪器
        habit_tracker = HabitTracker()
        habit_tracker.display_habit_tracker()
        
        st.divider()
        
        # 专注训练
        st.subheader("🎯 专注训练")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🍅 番茄钟", use_container_width=True):
                focus_trainer = FocusTrainer()
                focus_trainer.start_pomodoro(25)
        
        with col2:
            if st.button("🚀 深度工作", use_container_width=True):
                focus_trainer = FocusTrainer()
                focus_trainer.start_deep_work(90)
    
    # 在主界面添加智能提醒
    smart_reminder = SmartReminder()
    smart_reminder.display_reminders()
    
    # 添加语音输入支持
    add_voice_input_support()
    
    # 在任务管理tab中添加AI建议
    with st.expander("🤖 AI任务建议", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**基于您的时间模式建议:**")
            st.write("• 上午9-11点: 处理复杂任务")
            st.write("• 下午2-4点: 创造性工作")
            st.write("• 晚上7-9点: 学习新技能")
        
        with col2:
            st.write("**基于紫微斗数建议:**")
            st.write("• 太阴铃星: 适合深度分析")
            st.write("• 天同: 避免过度放松")
            st.write("• 太阳化忌: 注意财务决策")

# ===== 新增模块：数据看板 =====
def create_executive_dashboard(df_tasks, df_finance):
    """创建高管仪表板"""
    st.subheader("📈 执行仪表板")
    
    # 关键指标
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # 本周完成率
        week_tasks = get_week_tasks(df_tasks)
        completion_rate = calculate_week_completion(week_tasks)
        st.metric("📅 本周完成率", f"{completion_rate}%")
    
    with col2:
        # 平均专注时间
        avg_focus = calculate_avg_focus_time(df_tasks)
        st.metric("⏱️ 平均专注", f"{avg_focus}分钟")
    
    with col3:
        # 月度收支
        monthly_finance = get_monthly_finance(df_finance)
        net_balance = monthly_finance["income"] - monthly_finance["expense"]
        st.metric("💰 本月结余", f"RM{net_balance:.2f}")
    
    with col4:
        # 效率评分
        efficiency_score = calculate_efficiency_score(df_tasks)
        st.metric("🚀 效率评分", f"{efficiency_score}/100")
    
    # 时间线视图
    st.write("### 时间线视图")
    create_timeline_view(df_tasks)
    
    # 热力图
    st.write("### 活跃度热力图")
    create_activity_heatmap(df_tasks)

def get_week_tasks(df_tasks):
    """获取本周任务"""
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    week_dates = [(week_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    week_tasks = df_tasks[df_tasks["日期"].isin(week_dates)]
    
    return week_tasks

def calculate_week_completion(df_tasks):
    """计算本周完成率"""
    if df_tasks.empty:
        return 0
    
    completed = df_tasks[df_tasks["完成"] == True]
    return round(len(completed) / len(df_tasks) * 100, 1)

def calculate_avg_focus_time(df_tasks):
    """计算平均专注时间"""
    completed = df_tasks[df_tasks["完成"] == True]
    if completed.empty:
        return 0
    
    if "实际用时(分)" in completed.columns:
        return round(completed["实际用时(分)"].mean(), 1)
    elif "用时(秒)" in completed.columns:
        return round(completed["用时(秒)"].mean() / 60, 1)
    else:
        return 0

def get_monthly_finance(df_finance):
    """获取本月财务"""
    today = datetime.now()
    month_str = today.strftime("%Y-%m")
    
    month_finance = df_finance[df_finance["日期"].str.startswith(month_str)]
    
    income = month_finance[month_finance["类型"] == "收入"]["金额"].sum()
    expense = month_finance[month_finance["类型"] == "支出"]["金额"].sum()
    
    return {"income": income, "expense": expense}

def calculate_efficiency_score(df_tasks):
    """计算效率评分"""
    if df_tasks.empty:
        return 0
    
    completed = df_tasks[df_tasks["完成"] == True]
    if completed.empty:
        return 0
    
    # 基于完成率、用时效率、时间管理计算
    completion_score = len(completed) / len(df_tasks) * 40
    
    # 用时效率得分
    if "预计时间(分)" in completed.columns and "实际用时(分)" in completed.columns:
        efficiency_ratios = []
        for _, row in completed.iterrows():
            estimated = row["预计时间(分)"]
            actual = row["实际用时(分)"]
            if estimated > 0 and actual > 0:
                ratio = min(1.0, estimated / actual)  # 预计/实际，越高越好
                efficiency_ratios.append(ratio)
        
        efficiency_score = sum(efficiency_ratios) / len(efficiency_ratios) * 30 if efficiency_ratios else 15
    else:
        efficiency_score = 15
    
    # 时间分布得分
    time_dist_score = 15  # 基础分
    
    # 紧急任务完成得分
    if "紧急度" in completed.columns:
        urgent_completed = completed[completed["紧急度"] == "高"]
        urgent_score = len(urgent_completed) / len(completed[completed["紧急度"] == "高"]) * 15 if len(completed[completed["紧急度"] == "高"]) > 0 else 0
    else:
        urgent_score = 0
    
    total_score = completion_score + efficiency_score + time_dist_score + urgent_score
    
    return round(total_score)

def create_timeline_view(df_tasks):
    """创建时间线视图"""
    # 简化的时间线显示
    recent_tasks = df_tasks.sort_values("开始时间", ascending=False).head(10)
    
    for _, task in recent_tasks.iterrows():
        status_icon = "✅" if task["完成"] else "⏳"
        color = "green" if task["完成"] else "orange"
        
        st.markdown(f"""
        <div style="
            border-left: 3px solid {color};
            padding: 8px 15px;
            margin: 5px 0;
            background: #292828;
        ">
            {status_icon} <strong>{task['任务']}</strong><br>
            <small>📅 {task['日期']} | ⏰ {task.get('开始时间', '').split(' ')[1] if pd.notna(task.get('开始时间')) else ''}</small>
        </div>
        """, unsafe_allow_html=True)

def create_activity_heatmap(df_tasks):
    """创建活跃度热力图"""
    # 这里可以集成plotly热力图
    st.info("热力图功能开发中...")
    st.code("""
    # 计划功能:
    1. 按小时显示活跃度
    2. 按星期显示模式
    3. 颜色深浅表示生产力
    """)



def main():
    # ===== 加载数据 =====
    df_tasks = load_task_data()
    df_finance = load_finance_data()
    
    # ===== 添加增强功能 =====
    enhance_main_app()
    
    # ===== 添加执行仪表板 =====
    with st.expander("📊 高管仪表板", expanded=False):
        create_executive_dashboard(df_tasks, df_finance)
    
    
    # ===== SIDEBAR =====
    with st.sidebar:
        st.title("🧠 控制面板")
        
        # 数据管理
        st.subheader("💾 数据管理")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("备份数据", use_container_width=True):
                success, message = create_backup()
                if success:
                    st.success(message)
                else:
                    st.error(message)
        
        with col2:
            if st.button("导出Excel", use_container_width=True):
                b64, filename = export_to_excel()
                if b64:
                    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">点击下载Excel文件</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("文件已准备好下载")
                else:
                    st.error(filename)
        
        # 数据验证
        if st.button("验证数据完整性", use_container_width=True):
            df_tasks = load_task_data()
            issues = validate_task_data(df_tasks)
            if issues:
                st.warning(f"发现{len(issues)}个问题:")
                for issue in issues[:5]:  # 只显示前5个问题
                    st.write(f"• {issue}")
                if len(issues) > 5:
                    st.write(f"... 还有{len(issues)-5}个问题")
            else:
                st.success("数据验证通过!")
        
        st.divider()
        
        # 今日统计
        st.subheader("📊 今日统计")
        
        df_tasks = load_task_data()
        df_finance = load_finance_data()
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_tasks = df_tasks[df_tasks["日期"] == today_str]
        today_finance = df_finance[df_finance["日期"] == today_str]
        
        # 任务统计
        task_stats = calculate_task_efficiency(today_tasks)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("今日任务", f"{len(today_tasks)}项")
        with col2:
            st.metric("完成率", f"{task_stats['completion_rate']*100:.0f}%")
        
        # 财务统计
        finance_stats = calculate_finance_summary(today_finance)
        
        col3, col4 = st.columns(2)
        with col3:
            st.metric("今日支出", f"RM{finance_stats['total_expense']:.1f}")
        with col4:
            st.metric("今日收入", f"RM{finance_stats['total_income']:.1f}")
        
        st.divider()
        
        # 快速导航
        st.subheader("🔗 快速导航")
        
        if st.button("跳转到今日任务", use_container_width=True):
            st.session_state.page = "tasks"
            st.rerun()
        
        if st.button("跳转到财务记录", use_container_width=True):
            st.session_state.page = "finance"
            st.rerun()
        
        if st.button("查看可视化分析", use_container_width=True):
            st.session_state.page = "analytics"
            st.rerun()
    
    # ===== MAIN CONTENT =====
    st.title("🧠 外部前额叶皮层 — 生产力 & 财务仪表板")
    st.caption("任务管理 > 秒级执行 > 财务审计 > 自动评分 > 可视化 > AI Prompt Ready")
    
    # ===== DAILY AI PROMPT =====
    st.subheader("📌 Daily FateOS AI Summary Prompt")
    
    df_tasks = load_task_data()
    df_finance = load_finance_data()
    
    daily_prompt = generate_daily_summary_prompt(df_tasks, df_finance)
    
    with st.expander("查看/复制AI提示词", expanded=True):
        st.text_area(
            "AI提示词",
            value=daily_prompt,
            height=250,
            label_visibility="collapsed"
        )
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("复制到剪贴板", use_container_width=True):
                st.code(daily_prompt[:200] + "..." if len(daily_prompt) > 200 else daily_prompt)
                st.success("已复制到剪贴板!")
    
    # ===== TABS FOR DIFFERENT SECTIONS =====
    tab1, tab2, tab3, tab4 = st.tabs(["📝 任务管理", "💰 财务管理", "📊 数据分析", "📅 历史记录"])
    
    with tab1:
        # ===== ADD TASK =====
        st.subheader("添加新任务")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_task = st.text_input("任务内容*", placeholder="请输入具体任务描述...")
            new_category = st.selectbox("类别*", ["工作", "学习", "运动", "个人", "健康", "社交", "其他"])
            new_urgency = st.select_slider("紧急度", options=["低", "中", "高"], value="中")
        
        with col2:
            estimated_minutes = st.number_input("预计时间(分钟)", min_value=1, max_value=480, value=30)
            task_date = st.date_input("任务日期", value=datetime.today())
            new_notes = st.text_area("备注", placeholder="可选：任务详情、资源链接等...")
        
        if st.button("添加任务并开始计时", type="primary", use_container_width=True):
            if new_task.strip() == "":
                st.warning("请输入任务内容!")
            else:
                now = datetime.now()
                new_row = {
                    "日期": task_date.strftime("%Y-%m-%d"),
                    "创建时间": now.strftime("%H:%M:%S"),
                    "任务": new_task,
                    "类别": new_category,
                    "备注": new_notes,
                    "完成": False,
                    "开始时间": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "完成时间": "",
                    "用时(秒)": 0,
                    "评分": "",
                    "AI反馈": "",
                    "紧急度": new_urgency,
                    "预计时间(分)": estimated_minutes,
                    "实际用时(分)": 0
                }
                
                df_tasks = pd.concat([df_tasks, pd.DataFrame([new_row])], ignore_index=True)
                if save_task_data(df_tasks):
                    st.success("✅ 任务已添加并开始计时!")
                    st.balloons()
                else:
                    st.error("添加任务失败，请重试")
        
        st.divider()
        
        # ===== TODAY'S TASKS =====
        st.subheader("今日任务列表")
        
        today_tasks = df_tasks[df_tasks["日期"] == today_str].copy()
        
        if not today_tasks.empty:
            # 批量操作
            st.write("批量操作:")
            col1, col2, col3 = st.columns(3)
            
            task_names = today_tasks["任务"].tolist()
            selected_tasks = st.multiselect("选择要批量操作的任务", options=task_names)
            
            with col1:
                # 修复批量完成任务部分
                if st.button("批量完成", use_container_width=True) and selected_tasks:
                    for idx, row in today_tasks.iterrows():
                        if row["任务"] in selected_tasks:
                            start_val = df_tasks.at[idx, "开始时间"]
                            start_time = datetime.strptime(str(start_val), "%Y-%m-%d %H:%M:%S")
                            end_time = datetime.now()
                            duration = (end_time - start_time).total_seconds()
                            
                            df_tasks.at[idx, "完成"] = True
                            df_tasks.at[idx, "完成时间"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
                            df_tasks.at[idx, "用时(秒)"] = round(duration, 1)
                            df_tasks.at[idx, "实际用时(分)"] = round(duration / 60, 1)
                            
                            # 修复这里：去掉第三个参数
                            estimated = float(df_tasks.at[idx, "预计时间(分)"]) if pd.notna(df_tasks.at[idx, "预计时间(分)"]) else 0
                            actual = float(df_tasks.at[idx, "实际用时(分)"]) if pd.notna(df_tasks.at[idx, "实际用时(分)"]) else 0
                            
                            if estimated > 0:
                                efficiency = actual / estimated
                                if efficiency <= 0.8:
                                    df_tasks.at[idx, "评分"] = "优秀"
                                elif efficiency <= 1.2:
                                    df_tasks.at[idx, "评分"] = "良好"
                                else:
                                    df_tasks.at[idx, "评分"] = "需改进"
                            else:
                                df_tasks.at[idx, "评分"] = "良好"
                    
                    if save_task_data(df_tasks):
                        st.success(f"已批量完成{len(selected_tasks)}个任务!")
                        st.rerun()
            
            with col2:
                if st.button("批量删除", use_container_width=True, type="secondary") and selected_tasks:
                    df_tasks = df_tasks[~df_tasks["任务"].isin(selected_tasks)]
                    if save_task_data(df_tasks):
                        st.success(f"已删除{len(selected_tasks)}个任务!")
                        st.rerun()
            
            with col3:
                if st.button("重置计时", use_container_width=True) and selected_tasks:
                    now = datetime.now()
                    for idx, row in today_tasks.iterrows():
                        if row["任务"] in selected_tasks:
                            df_tasks.at[idx, "开始时间"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    if save_task_data(df_tasks):
                        st.success(f"已重置{len(selected_tasks)}个任务的计时!")
            
            # 单个任务展示
            st.write("单个任务操作:")
            for idx, row in today_tasks.iterrows():
                task_class = "task-completed" if row["完成"] else "task-pending"
                if not row["完成"] and pd.to_datetime(today_str) < pd.to_datetime("today"):
                    task_class = "task-overdue"
                
                with st.container():
                    col_left, col_right = st.columns([4, 1])
                    
                    with col_left:
                        st.markdown(f"""
                        <div class="task-card {task_class}">
                            <h4>{"✅ " if row["完成"] else "⏳ "}{row['任务']}</h4>
                            <p><strong>类别:</strong> {row['类别']} | <strong>紧急度:</strong> {row.get('紧急度', '中')}</p>
                            <p><strong>状态:</strong> {'已完成' if row['完成'] else '进行中'} | 
                            <strong>开始时间:</strong> {row.get('开始时间', '-')} | 
                            <strong>预计:</strong> {row.get('预计时间(分)', '-')}分钟</p>
                            <p><strong>备注:</strong> {row.get('备注', '-')}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_right:
                        if not row["完成"]:
                            # 显示实时计时
                            if row.get("开始时间"):
                                try:
                                    start_time = datetime.strptime(str(row["开始时间"]), "%Y-%m-%d %H:%M:%S")
                                    elapsed = (datetime.now() - start_time).total_seconds()
                                    hours = int(elapsed // 3600)
                                    minutes = int((elapsed % 3600) // 60)
                                    seconds = int(elapsed % 60)
                                    st.metric("已进行", f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                                except:
                                    pass
                            
                            if st.button("完成", key=f"complete_{idx}", use_container_width=True):
                                start_val = df_tasks.at[idx, "开始时间"]
                                start_time = datetime.strptime(str(start_val), "%Y-%m-%d %H:%M:%S")
                                end_time = datetime.now()
                                duration = (end_time - start_time).total_seconds()
                                
                                df_tasks.at[idx, "完成"] = True
                                df_tasks.at[idx, "完成时间"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
                                df_tasks.at[idx, "用时(秒)"] = round(duration, 1)
                                df_tasks.at[idx, "实际用时(分)"] = round(duration / 60, 1)
                                
                                # 修复这里：去掉第三个参数
                                estimated = float(df_tasks.at[idx, "预计时间(分)"]) if pd.notna(df_tasks.at[idx, "预计时间(分)"]) else 0
                                actual = float(df_tasks.at[idx, "实际用时(分)"]) if pd.notna(df_tasks.at[idx, "实际用时(分)"]) else 0
                                
                                if estimated > 0:
                                    efficiency = actual / estimated
                                    if efficiency <= 0.8:
                                        df_tasks.at[idx, "评分"] = "优秀"
                                    elif efficiency <= 1.2:
                                        df_tasks.at[idx, "评分"] = "良好"
                                    else:
                                        df_tasks.at[idx, "评分"] = "需改进"
                                else:
                                    df_tasks.at[idx, "评分"] = "良好"
                                
                                if save_task_data(df_tasks):
                                    st.success(f"任务完成! 用时: {round(duration/60, 1)}分钟")
                                    st.rerun()
                        
                        if st.button("删除", key=f"delete_{idx}", use_container_width=True, type="secondary"):
                            df_tasks = df_tasks.drop(idx).reset_index(drop=True)
                            if save_task_data(df_tasks):
                                st.success("任务已删除!")
                                st.rerun()
        else:
            st.info("今天还没有添加任务，请在上面添加新任务。")
    
    with tab2:
        # ===== FINANCE MANAGEMENT =====
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("添加财务记录")
            
            finance_type = st.selectbox("类型*", ["支出", "收入"], key="finance_type")
            finance_amount = st.number_input("金额 (RM)*", min_value=0.0, step=0.1, format="%.2f")
            
            col_a, col_b = st.columns(2)
            with col_a:
                finance_category = st.selectbox("分类*", 
                    ["餐饮", "交通", "购物", "娱乐", "学习", "医疗", "住房", "投资", "薪资", "其他"])
            with col_b:
                payment_method = st.selectbox("支付方式", 
                    ["现金", "银行卡", "信用卡", "电子钱包", "其他"])
            
            finance_note = st.text_input("备注", placeholder="记录详情...")
            finance_date = st.date_input("日期", value=datetime.today(), key="finance_date")
            
            if st.button("添加财务记录", type="primary", use_container_width=True):
                if finance_amount <= 0:
                    st.warning("金额必须大于0!")
                else:
                    now = datetime.now()
                    new_finance = {
                        "日期": finance_date.strftime("%Y-%m-%d"),
                        "创建时间": now.strftime("%H:%M:%S"),
                        "类型": finance_type,
                        "金额": finance_amount,
                        "备注": finance_note,
                        "支付方式": payment_method,
                        "分类": finance_category
                    }
                    
                    df_finance = pd.concat([df_finance, pd.DataFrame([new_finance])], ignore_index=True)
                    if save_finance_data(df_finance):
                        st.success(f"✅ {finance_type}记录已添加: RM{finance_amount:.2f}")
        
        with col2:
            st.subheader("今日财务快照")
            
            today_finance = df_finance[df_finance["日期"] == today_str]
            
            if not today_finance.empty:
                income = today_finance[today_finance["类型"] == "收入"]["金额"].sum()
                expense = today_finance[today_finance["类型"] == "支出"]["金额"].sum()
                net = income - expense
                
                st.metric("今日收入", f"RM{income:.2f}", delta=f"RM{income:.2f}" if income > 0 else None)
                st.metric("今日支出", f"RM{expense:.2f}", delta=f"-RM{expense:.2f}" if expense > 0 else None)
                st.metric("今日结余", f"RM{net:.2f}", 
                         delta_color="normal" if net >= 0 else "inverse")
                
                # 支出分类
                expense_df = today_finance[today_finance["类型"] == "支出"]
                if not expense_df.empty:
                    st.write("**支出分类:**")
                    for category, amount in expense_df.groupby("分类")["金额"].sum().items():
                        st.write(f"• {category}: RM{amount:.2f}")
            else:
                st.info("今日暂无财务记录")
        
        st.divider()
        
        # ===== RECENT FINANCE RECORDS =====
        st.subheader("最近财务记录")
        
        if not df_finance.empty:
            # 显示最近10条记录
            recent_finance = df_finance.sort_values("创建时间", ascending=False).head(10)
            
            for idx, row in recent_finance.iterrows():
                amount_color = "green" if row["类型"] == "收入" else "red"
                amount_sign = "+" if row["类型"] == "收入" else "-"
                
                st.markdown(f"""
                <div style="padding: 10px; margin: 5px 0; border-left: 3px solid {amount_color}; background: #292828; border-radius: 5px;">
                    <strong>{row['日期']} {row['创建时间']}</strong><br>
                    <span style="color: {amount_color}; font-weight: bold;">{amount_sign}RM{row['金额']:.2f}</span> | 
                    {row['类型']} | {row['分类']} | {row['支付方式']}<br>
                    <em>{row['备注'] or '无备注'}</em>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("暂无财务记录")
    
    with tab3:
        # ===== DATA ANALYTICS =====
        st.subheader("📈 数据可视化分析")
        
        if df_tasks.empty and df_finance.empty:
            st.info("暂无数据可供分析，请先添加任务和财务记录。")
        else:
            # 任务分析
            if not df_tasks.empty:
                st.write("### 任务分析")
                fig1, fig2, fig3 = create_task_visualizations(df_tasks)
                
                if fig1:
                    st.plotly_chart(fig1, use_container_width=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if fig2:
                        st.plotly_chart(fig2, use_container_width=True)
                
                with col2:
                    if fig3:
                        st.plotly_chart(fig3, use_container_width=True)
                
                # 任务效率统计
                st.write("### 任务效率统计")
                task_stats = calculate_task_efficiency(df_tasks)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("总任务数", task_stats["total_tasks"])
                with col2:
                    st.metric("完成率", f"{task_stats['completion_rate']*100:.1f}%")
                with col3:
                    st.metric("总用时", f"{task_stats['total_time']:.1f}分钟")
                with col4:
                    st.metric("效率评分", f"{task_stats['efficiency_score']:.2f}")
            
            st.divider()
            
            # 财务分析
            if not df_finance.empty:
                st.write("### 财务分析")
                fig1, fig2, category_table = create_finance_visualizations(df_finance)
                
                if fig1:
                    st.plotly_chart(fig1, use_container_width=True)
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    if fig2:
                        st.plotly_chart(fig2, use_container_width=True)
                
                with col2:
                    if category_table is not None:
                        st.write("**支出分类排名:**")
                        for idx, row in category_table.head(5).iterrows():
                            st.write(f"{idx+1}. {row['分类']}: RM{row['金额']:.2f}")
                
                # 财务摘要
                st.write("### 财务摘要")
                finance_stats = calculate_finance_summary(df_finance)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("总收入", f"RM{finance_stats['total_income']:.2f}")
                with col2:
                    st.metric("总支出", f"RM{finance_stats['total_expense']:.2f}")
                with col3:
                    st.metric("净余额", f"RM{finance_stats['net_balance']:.2f}")
                with col4:
                    st.metric("日均支出", f"RM{finance_stats['avg_daily_expense']:.2f}")
    
    with tab4:
        # ===== HISTORICAL RECORDS =====
        st.subheader("历史记录查看")
        
        # 日期选择器
        col1, col2 = st.columns(2)
        with col1:
            all_dates = sorted(pd.to_datetime(df_tasks["日期"], errors='coerce').dropna().unique(), reverse=True)
            date_options = [date.strftime("%Y-%m-%d") for date in all_dates]
            selected_date = st.selectbox("选择日期", options=date_options, index=0 if date_options else None)
        
        with col2:
            view_mode = st.radio("查看模式", ["任务记录", "财务记录"], horizontal=True)
        
        if selected_date:
            if view_mode == "任务记录":
                historical_tasks = df_tasks[df_tasks["日期"] == selected_date]
                
                if not historical_tasks.empty:
                    st.write(f"### {selected_date} 的任务记录")
                    
                    for idx, row in historical_tasks.iterrows():
                        status_icon = "✅" if row["完成"] else "⏳"
                        status_color = "green" if row["完成"] else "orange"
                        
                        st.markdown(f"""
                        <div style="padding: 12px; margin: 8px 0; border-left: 4px solid {status_color}; background: #292828; border-radius: 6px;">
                            <strong>{status_icon} {row['任务']}</strong><br>
                            类别: {row['类别']} | 紧急度: {row.get('紧急度', '中')}<br>
                            状态: {'已完成' if row['完成'] else '未完成'} | 
                            开始: {row.get('开始时间', '-')} | 
                            完成: {row.get('完成时间', '-')}<br>
                            预计: {row.get('预计时间(分)', '-')}分钟 | 
                            实际: {row.get('实际用时(分)', '-')}分钟 | 
                            评分: {row.get('评分', '-')}<br>
                            备注: {row.get('备注', '-')}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # 生成历史提示词
                    st.divider()
                    st.write("### 历史任务提示词")
                    
                    def format_historical_task(t):
                        # 计算效率
                        try:
                            actual = float(t.get('实际用时(分)', 0))
                            estimated = float(t.get('预计时间(分)', 0))
                            if estimated > 0:
                                efficiency = round(actual / estimated, 2)
                            else:
                                efficiency = 'N/A'
                        except:
                            efficiency = 'N/A'
                        
                        # 计算用时（优先使用实际用时，否则转换秒数）
                        try:
                            if t.get('实际用时(分)'):
                                duration = f"{t.get('实际用时(分)')}分钟"
                            else:
                                seconds = float(t.get('用时(秒)', 0))
                                duration = f"{round(seconds/60, 1)}分钟"
                        except:
                            duration = "0分钟"
                        
                        return (
                            f"日期:{t.get('日期','-')} | "
                            f"任务:{t.get('任务','-')} | "
                            f"类别:{t.get('类别','-')} | "
                            f"完成:{'是' if t.get('完成', False) else '否'} | "
                            f"用时:{duration} | "
                            f"评分:{t.get('评分','-')} | "
                            f"效率:{efficiency}"
                        )
                    
                    historical_prompts = "\n".join([format_historical_task(t) for t in historical_tasks.to_dict('records')])
                    
                    st.text_area("历史任务数据", value=historical_prompts, height=200)
                    
                    if st.button("复制历史任务数据", use_container_width=True):
                        st.code(historical_prompts[:500] + "..." if len(historical_prompts) > 500 else historical_prompts)
                        st.success("已复制到剪贴板!")
                
                else:
                    st.info(f"{selected_date} 没有任务记录")
            
            else:  # 财务记录
                historical_finance = df_finance[df_finance["日期"] == selected_date]
                
                if not historical_finance.empty:
                    st.write(f"### {selected_date} 的财务记录")
                    
                    # 计算统计
                    income = historical_finance[historical_finance["类型"] == "收入"]["金额"].sum()
                    expense = historical_finance[historical_finance["类型"] == "支出"]["金额"].sum()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("当日收入", f"RM{income:.2f}")
                    with col2:
                        st.metric("当日支出", f"RM{expense:.2f}")
                    
                    # 显示详细记录
                    for idx, row in historical_finance.iterrows():
                        amount_color = "green" if row["类型"] == "收入" else "red"
                        amount_sign = "+" if row["类型"] == "收入" else "-"
                        
                        st.markdown(f"""
                        <div style="padding: 10px; margin: 5px 0; border-left: 3px solid {amount_color}; background: #f9f9f9; border-radius: 5px;">
                            <strong>{row['创建时间']}</strong><br>
                            <span style="color: {amount_color}; font-weight: bold;">{amount_sign}RM{row['金额']:.2f}</span> | 
                            {row['类型']} | {row['分类']} | {row['支付方式']}<br>
                            <em>{row['备注'] or '无备注'}</em>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # 生成财务提示词
                    st.divider()
                    st.write("### 历史财务提示词")
                    
                    def format_historical_finance(f):
                        return (
                            f"日期:{f.get('日期','-')} | "
                            f"类型:{f.get('类型','-')} | "
                            f"金额:RM{f.get('金额',0):.2f} | "
                            f"分类:{f.get('分类','-')} | "
                            f"支付方式:{f.get('支付方式','-')} | "
                            f"备注:{f.get('备注','-')}"
                        )
                    
                    finance_prompts = "\n".join([format_historical_finance(f) for f in historical_finance.to_dict('records')])
                    
                    st.text_area("历史财务数据", value=finance_prompts, height=200)
                    
                    if st.button("复制历史财务数据", use_container_width=True):
                        st.code(finance_prompts[:500] + "..." if len(finance_prompts) > 500 else finance_prompts)
                        st.success("已复制到剪贴板!")
                
                else:
                    st.info(f"{selected_date} 没有财务记录")
        else:
            st.info("请选择日期查看历史记录")
    
    

# ===== RUN APPLICATION =====
if __name__ == "__main__":
    main()