using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using System.Text.Json;

internal static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        if(args.Contains("--placement-self-test")){
            var area=new Rectangle(0,0,1920,1080);
            if(WindowPlacement.Fit(new Rectangle(100,80,1400,900),area)!=new Rectangle(100,80,1400,900))throw new Exception("Normal placement changed");
            if(WindowPlacement.Fit(new Rectangle(4000,-200,2500,1500),area)!=area)throw new Exception("Offscreen placement not fitted");
            if(WindowPlacement.Fit(new Rectangle(-1800,50,1400,900),new Rectangle(-1920,0,1920,1080))!=new Rectangle(-1800,50,1400,900))throw new Exception("Secondary monitor placement changed");
            File.WriteAllText(Path.Combine(AppContext.BaseDirectory,"placement-test.txt"),"PASS normal/offscreen/negative-monitor");return;
        }
        if(args.Contains("--log-self-test")){AppDebugLog.DirectoryOverride=Path.Combine(AppContext.BaseDirectory,"debug-selftest");AppDebugLog.Write("test","panel_closed");AppDebugLog.Write("test","connection_failed",new HttpRequestException("sensitive text must not appear"));return;}
        ApplicationConfiguration.Initialize();
        if(args.Contains("--ime-self-test")){
            using var testForm=new Form{ImeMode=ImeMode.NoControl};
            using var testView=new WebView2{ImeMode=ImeMode.NoControl};
            using var testContext=new Label{TabStop=false};
            testForm.Controls.Add(testView);testForm.Controls.Add(testContext);
            File.WriteAllText(Path.Combine(AppContext.BaseDirectory,"ime-values.json"),JsonSerializer.Serialize(new{form=testForm.ImeMode.ToString(),view=testView.ImeMode.ToString(),context=testContext.ImeMode.ToString()}));
            if(testForm.ImeMode!=ImeMode.NoControl||testView.ImeMode!=ImeMode.NoControl||testContext.TabStop||testContext.CanSelect)throw new Exception("IME policy mismatch");
            File.WriteAllText(Path.Combine(AppContext.BaseDirectory,"ime-test.txt"),"PASS neutral IME host/WebView/context; read-only context excluded from tab focus");return;
        }
        Application.ThreadException+=(_,e)=>AppDebugLog.Write("native","ui_exception",e.Exception);
        TaskScheduler.UnobservedTaskException+=(_,e)=>AppDebugLog.Write("native","task_exception",e.Exception);
        AppDebugLog.Write("native","startup");
        var form = new Form { Text = "Game Making Desk · 이야기 작업실", ImeMode=ImeMode.NoControl, Width = 1320, Height = 940, MinimumSize = new Size(860, 640), StartPosition = FormStartPosition.CenterScreen, BackColor = Color.FromArgb(18,20,23) };
        try { form.Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!); } catch { }
        var view = new WebView2 { ImeMode=ImeMode.NoControl, Dock = DockStyle.Fill, DefaultBackgroundColor = Color.FromArgb(18,20,23) };
        bool closingPrepared=false;
        form.FormClosing+=async(_,e)=>{if(closingPrepared||view.CoreWebView2 is null)return;e.Cancel=true;try{await view.ExecuteScriptAsync("window.deskPrepareUpdate?.()");}catch{}closingPrepared=true;form.Close();};
        var notify = new NotifyIcon { Icon=form.Icon??SystemIcons.Application, Text="Game Making Desk · 이야기 노트", Visible=true };
        notify.BalloonTipClicked+=async(_,_)=>{form.Show();if(form.WindowState==FormWindowState.Minimized)form.WindowState=FormWindowState.Normal;form.Activate();try{await view.ExecuteScriptAsync("window.dispatchEvent(new Event('desk-open-mission'))");}catch{}};
        form.FormClosed+=(_,_)=>notify.Dispose();
        form.Width = 1540;
        WindowPlacement.Attach(form,"main");
        var split = new SplitContainer { ImeMode=ImeMode.NoControl, Dock=DockStyle.Fill, Size=new Size(1520,900), SplitterWidth=5, SplitterDistance=900, Panel1MinSize=520, Panel2MinSize=320, BackColor=Color.FromArgb(59,66,66) };
        var chat = new WebView2 { ImeMode=ImeMode.NoControl, Dock=DockStyle.Fill, DefaultBackgroundColor=Color.FromArgb(18,20,23) };
        var sideHead = new Panel { ImeMode=ImeMode.NoControl, Dock=DockStyle.Top, Height=110 };
        var closeChat = new Button { Dock=DockStyle.Right, Width=36, Text="×", Font=new Font("Segoe UI",15), FlatStyle=FlatStyle.Flat, ForeColor=Color.FromArgb(166,175,180), BackColor=Color.FromArgb(25,30,32), AccessibleName="OnlyChat 패널 닫기", Cursor=Cursors.Hand };
        closeChat.FlatAppearance.BorderSize=0;
        closeChat.FlatAppearance.MouseOverBackColor=Color.FromArgb(45,52,56);
        var panelTip=new ToolTip();panelTip.SetToolTip(closeChat,"OnlyChat 패널 닫기 · AI 작업은 계속됩니다");form.FormClosed+=(_,_)=>panelTip.Dispose();
        var context = new Label { TabStop=false, AutoEllipsis=true, Dock=DockStyle.Fill, BackColor=Color.FromArgb(25,30,32), ForeColor=Color.LightGray };
        var feedback = new Button { Dock=DockStyle.Bottom, Height=32, Text="현재 페이지 피드백 · 메모 복사 / OnlyChat 연결", FlatStyle=FlatStyle.Flat, ForeColor=Color.Wheat };
        sideHead.Controls.Add(context); sideHead.Controls.Add(feedback); sideHead.Controls.Add(closeChat);
        split.Panel1.Controls.Add(view); split.Panel2.Controls.Add(chat); split.Panel2.Controls.Add(sideHead); form.Controls.Add(split);
        string noteContext="";
        var panelState=Path.GetFullPath(Path.Combine(AppContext.BaseDirectory,"../onlychat-panel-state.json"));
        void SetPanel(bool open){
            split.Panel2Collapsed=!open;
            try{File.WriteAllText(panelState+".tmp",JsonSerializer.Serialize(new{open}));File.Move(panelState+".tmp",panelState,true);}catch(Exception ex){AppDebugLog.Write("onlychat","panel_state_save_failed",ex);}
            AppDebugLog.Write("onlychat",open?"panel_opened":"panel_closed");
            if(view.CoreWebView2!=null)_=view.ExecuteScriptAsync("window.dispatchEvent(new CustomEvent('desk-onlychat-state',{detail:{open:"+(open?"true":"false")+"}}))");
        }
        try{if(File.Exists(panelState)){using var state=JsonDocument.Parse(File.ReadAllText(panelState));split.Panel2Collapsed=!state.RootElement.GetProperty("open").GetBoolean();}}catch(Exception ex){AppDebugLog.Write("onlychat","panel_state_read_failed",ex);}
        closeChat.Click+=(_,_)=>SetPanel(false);
        async Task OpenChat() {
            using var http=new HttpClient {Timeout=TimeSpan.FromSeconds(2)};
            try { using var response=await http.GetAsync("http://127.0.0.1:8899/api/health"); response.EnsureSuccessStatusCode(); chat.CoreWebView2.Navigate("http://127.0.0.1:8899/"); AppDebugLog.Write("onlychat","connected"); }
            catch(Exception ex) { AppDebugLog.Write("onlychat","connection_failed",ex);chat.CoreWebView2.NavigateToString("<html style='background:#191e20;color:#ddd;font:15px sans-serif;padding:24px'><h2>OnlyChat 연결 대기</h2><p>현재 페이지는 위에 실시간으로 표시됩니다.</p><p>OnlyChat 로컬 API(8899)가 응답하지 않습니다. 오른쪽 위 닫기 버튼으로 패널을 접을 수 있습니다.</p></html>"); }
        }
        feedback.Click+=async(_,_)=>{ if(!string.IsNullOrWhiteSpace(noteContext)) Clipboard.SetText("이 게임 기획 메모에 피드백해 줘. 제안과 확정된 설정을 구분하고 학교 과제 목표에 연결해 줘.\n\n"+noteContext); await OpenChat(); feedback.Text="메모 복사됨 · OnlyChat에 Ctrl+V 후 전송 / 재연결"; };
        form.Shown += async (_, _) => {
            try {
                var dataPath = Environment.GetEnvironmentVariable("GAME_MAKING_DESK_PROFILE") ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "GameMakingDesk", "WebView2");
                var environment = await CoreWebView2Environment.CreateAsync(null, dataPath);
                await view.EnsureCoreWebView2Async(environment);
                await chat.EnsureCoreWebView2Async(environment);
                view.CoreWebView2.NavigationCompleted+=(_,e)=>{if(!e.IsSuccess)AppDebugLog.Write("webview","navigation_failed",details:new{status=e.WebErrorStatus.ToString()});else _=view.ExecuteScriptAsync("window.dispatchEvent(new CustomEvent('desk-onlychat-state',{detail:{open:"+(!split.Panel2Collapsed?"true":"false")+"}}))");};
                view.CoreWebView2.ProcessFailed+=(_,e)=>AppDebugLog.Write("webview","process_failed",details:new{kind=e.ProcessFailedKind.ToString()});
                view.CoreWebView2.WebMessageReceived+=async(_,e)=>{try{if(!e.Source.StartsWith("http://127.0.0.1:8767/"))return;using var data=JsonDocument.Parse(e.WebMessageAsJson);var type=data.RootElement.GetProperty("type").GetString();if(type=="toggle-onlychat"){SetPanel(split.Panel2Collapsed);if(!split.Panel2Collapsed)await OpenChat();}else if(type=="client-debug"){var code=data.RootElement.GetProperty("code").GetString();if(new[]{"js_error","promise_error","api_error","live_update_failed"}.Contains(code))AppDebugLog.Write("client",code!);}else if(type=="new-mission"){notify.BalloonTipTitle="이야기 노트 · 새 미션";notify.BalloonTipText=data.RootElement.GetProperty("title").GetString()??"새 기록이 도착했습니다.";notify.ShowBalloonTip(6000);}}catch(Exception ex){AppDebugLog.Write("native","web_message_failed",ex);}};
                var sync=new System.Windows.Forms.Timer {Interval=2000};
                sync.Tick+=async(_,_)=>{try{var raw=await view.ExecuteScriptAsync("(document.querySelector('h1')?.innerText||'')+'\\n\\n'+(document.querySelector('#idea')?.value||'')");noteContext=JsonSerializer.Deserialize<string>(raw)??"";if(context.Text!=noteContext)context.Text=noteContext;}catch(Exception ex){AppDebugLog.Write("onlychat","context_sync_failed",ex);}};
                sync.Start();form.FormClosed+=(_,_)=>sync.Dispose();
                view.CoreWebView2.Settings.AreDevToolsEnabled = false;
                view.CoreWebView2.Settings.IsStatusBarEnabled = false;
                view.CoreWebView2.NewWindowRequested += (_, e) => { e.Handled = true; var child = new Form { Text="이미지 보기", Width=1100, Height=800, MinimumSize=new Size(860,640), BackColor=Color.FromArgb(18,20,23) }; WindowPlacement.Attach(child,"image"); var imageView=new WebView2 {Dock=DockStyle.Fill,Source=new Uri(e.Uri)}; child.Controls.Add(imageView); child.Show(form); };
                view.CoreWebView2.Navigate("http://127.0.0.1:8767/");
                if(!split.Panel2Collapsed)await OpenChat();
            } catch (Exception ex) { AppDebugLog.Write("native","startup_failed",ex);MessageBox.Show(form, "작업실을 열지 못했습니다. WebView2 Runtime과 로컬 서버를 확인해 주세요.\n" + ex.Message, "작업실 연결 확인"); }
        };
        Application.Run(form);
    }
}
