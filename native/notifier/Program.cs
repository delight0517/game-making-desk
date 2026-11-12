using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

internal static class Program
{
    [STAThread] static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        string root=Path.GetFullPath(Path.Combine(AppContext.BaseDirectory,".."));
        using var single=new Mutex(true,"Local\\LavaDeskNotify-"+Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(root)))[..16],out bool first);
        if(!first)return;
        Application.Run(new Watcher(root,args.Contains("--test-popup")));
    }
}

sealed class Watcher:ApplicationContext
{
    readonly string root,statePath;
    readonly HttpClient client=new(){Timeout=TimeSpan.FromSeconds(3)};
    readonly System.Windows.Forms.Timer poll=new(){Interval=2500};
    readonly NotifyIcon tray;
    readonly HashSet<string> seen=new();
    Popup? popup;
    bool polling, initialized, closing;
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h,int command);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
    public Watcher(string root,bool test)
    {
        this.root=root;statePath=Path.Combine(root,"notification-state.json");
        try{if(File.Exists(statePath))foreach(var id in JsonSerializer.Deserialize<string[]>(File.ReadAllText(statePath))??[])seen.Add(id);}catch{}
        var menu=new ContextMenuStrip();menu.Items.Add("팝업 테스트",null,(_,_)=>Show("팝업 알림 테스트","작업실이 뒤에 있어도 이 알림이 화면에 표시됩니다."));menu.Items.Add("작업실 열기",null,(_,_)=>OpenDesk());menu.Items.Add("알림 종료",null,(_,_)=>ExitThread());
        tray=new NotifyIcon{Text="게임 작업실 · 화면 알림",Icon=SystemIcons.Information,Visible=true,ContextMenuStrip=menu};
        poll.Tick+=async(_,_)=>await Tick();poll.Start();
        if(test)Show("윈도우 팝업 알림 연결됨","새 질문과 기획 작업 결과를 이 팝업으로 알려 드릴게요. 작성 중인 앱의 포커스는 유지됩니다.");
        _=Tick();
    }
    void Log(string code)
    {
        try{Directory.CreateDirectory(Path.Combine(root,"debug"));File.AppendAllText(Path.Combine(root,"debug","desktop-notifications.jsonl"),JsonSerializer.Serialize(new{at=DateTimeOffset.UtcNow,pid=Environment.ProcessId,code})+Environment.NewLine);}catch{}
    }
    void Save(){try{File.WriteAllText(statePath+".tmp",JsonSerializer.Serialize(seen.TakeLast(240)));File.Move(statePath+".tmp",statePath,true);}catch{Log("state_save_failed");}}
    static string Value(JsonElement obj,string key)=>obj.TryGetProperty(key,out var val)&&val.ValueKind==JsonValueKind.String?val.GetString()??"":"";
    bool Record(string id){if(string.IsNullOrEmpty(id)||!seen.Add(id))return false;Save();return true;}
    async Task Tick()
    {
        if(polling||closing)return;polling=true;
        try
        {
            using var response=await client.GetAsync("http://127.0.0.1:8767/api/desk");response.EnsureSuccessStatusCode();
            using var doc=JsonDocument.Parse(await response.Content.ReadAsStringAsync());if(closing)return;
            var data=doc.RootElement;var brief=data.GetProperty("brief");var id=Value(brief,"activeQuestionId");
            if(!initialized){Record("question:"+id);if(data.TryGetProperty("agent",out var initial)){var jobId=Value(initial,"id");if(jobId!="")Record("job:"+jobId+":"+Value(initial,"status"));}initialized=true;Log("watcher_ready");return;}
            if(Record("question:"+id))
            {
                string title="새 질문이 준비됐어요";
                foreach(var q in brief.GetProperty("questions").EnumerateArray())if(Value(q,"id")==id){title=Value(q,"title");break;}
                Show("게임 작업실 · 새 질문",title);
            }
            if(data.TryGetProperty("agent",out var agent))
            {
                string status=Value(agent,"status"),jobId=Value(agent,"id");
                if(jobId!=""&&status is "completed" or "needs_review" or "failed" or "interrupted")
                    if(Record("job:"+jobId+":"+status))Show(status=="completed"?"AI 기획 작업 완료":"AI 작업 확인 필요",status=="completed"?"기획 초안과 다음 작업이 준비됐어요. 작업실에서 검토해 주세요.":"작업이 멈췄거나 검토가 필요해요. 작성한 내용은 작업실에서 확인할 수 있습니다.");
            }
        }
        catch{ /* Temporary server outages do not produce repeated popups. */ }
        finally{polling=false;}
    }
    void Show(string title,string message)
    {
        if(closing)return;
        if(popup is {IsDisposed:false}){popup.UpdateMessage(title,message);Log("popup_updated");return;}
        popup=new Popup(title,message,OpenDesk);
        popup.Shown+=(_,_)=>Log("popup_shown");popup.Show();
    }
    void OpenDesk()
    {
        Log("popup_open_clicked");
        var exe=Path.Combine(root,"app","GameMakingDesk.exe");
        foreach(var process in Process.GetProcessesByName("GameMakingDesk"))
        {
            try{if(process.MainModule?.FileName==exe&&process.MainWindowHandle!=IntPtr.Zero){if(IsIconic(process.MainWindowHandle))ShowWindow(process.MainWindowHandle,9);SetForegroundWindow(process.MainWindowHandle);popup?.Close();return;}}catch{}
            finally{process.Dispose();}
        }
        try{Process.Start(new ProcessStartInfo(exe){WorkingDirectory=root,UseShellExecute=false});popup?.Close();}catch{Log("open_failed");}
    }
    protected override void ExitThreadCore(){closing=true;poll.Stop();poll.Dispose();client.Dispose();popup?.Close();tray.Visible=false;tray.Dispose();Save();base.ExitThreadCore();}
}

sealed class Popup:Form
{
    readonly Label title=new(),message=new();
    readonly System.Windows.Forms.Timer dismiss=new(){Interval=18000};
    protected override bool ShowWithoutActivation=>true;
    protected override CreateParams CreateParams{get{var cp=base.CreateParams;cp.ExStyle|=0x08000000|0x80;return cp;}}
    public Popup(string heading,string body,Action open)
    {
        FormBorderStyle=FormBorderStyle.None;ShowInTaskbar=false;TopMost=true;BackColor=Color.FromArgb(26,31,35);ForeColor=Color.FromArgb(234,227,215);Font=new Font("Malgun Gothic",10);
        var area=Screen.PrimaryScreen!.WorkingArea;Size=new Size(Math.Min(410,area.Width-24),194);Location=new Point(area.Right-Width-18,area.Bottom-Height-18);StartPosition=FormStartPosition.Manual;
        title.SetBounds(20,18,Width-65,30);title.Font=new Font(Font,FontStyle.Bold);message.SetBounds(20,55,Width-40,76);message.ForeColor=Color.FromArgb(183,190,192);
        var close=new Button{Text="×",FlatStyle=FlatStyle.Flat,ForeColor=ForeColor,Bounds=new Rectangle(Width-43,10,32,30),AccessibleName="알림 닫기"};close.FlatAppearance.BorderSize=0;close.Click+=(_,_)=>Close();
        var go=new Button{Text="작업실 열기  ↗",FlatStyle=FlatStyle.Flat,ForeColor=Color.FromArgb(231,180,120),Bounds=new Rectangle(18,143,160,34)};go.FlatAppearance.BorderSize=0;go.Click+=(_,_)=>open();
        Controls.AddRange([title,message,close,go]);UpdateMessage(heading,body);dismiss.Tick+=(_,_)=>Close();dismiss.Start();MouseEnter+=(_,_)=>dismiss.Stop();MouseLeave+=(_,_)=>dismiss.Start();FormClosed+=(_,_)=>dismiss.Dispose();
    }
    public void UpdateMessage(string heading,string body){title.Text=heading;message.Text=body;dismiss.Stop();dismiss.Start();}
}
