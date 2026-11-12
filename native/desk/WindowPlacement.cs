using System.Text.Json;

internal static class WindowPlacement
{
    internal record Placement(int X, int Y, int Width, int Height, bool Maximized);
    internal static Rectangle Fit(Rectangle bounds, Rectangle area)
    {
        int width=Math.Clamp(bounds.Width, Math.Min(860,area.Width), area.Width);
        int height=Math.Clamp(bounds.Height, Math.Min(640,area.Height), area.Height);
        return new Rectangle(Math.Clamp(bounds.X,area.Left,area.Right-width), Math.Clamp(bounds.Y,area.Top,area.Bottom-height),width,height);
    }
    internal static void Attach(Form form, string name)
    {
        var path=Path.GetFullPath(Path.Combine(AppContext.BaseDirectory,"../window-"+name+".json"));
        try
        {
            if(File.Exists(path))
            {
                var saved=JsonSerializer.Deserialize<Placement>(File.ReadAllText(path));
                if(saved!=null)
                {
                    var bounds=new Rectangle(saved.X,saved.Y,saved.Width,saved.Height);
                    var area=Screen.FromRectangle(bounds).WorkingArea;
                    form.StartPosition=FormStartPosition.Manual;
                    form.Bounds=Fit(bounds,area);
                    if(saved.Maximized)form.WindowState=FormWindowState.Maximized;
                }
            }
        }
        catch(Exception ex){AppDebugLog.Write("window","placement_read_failed",ex);}
        bool shown=false;
        var timer=new System.Windows.Forms.Timer{Interval=350};
        void Save()
        {
            if(!shown||form.WindowState==FormWindowState.Minimized)return;
            var bounds=form.WindowState==FormWindowState.Normal?form.Bounds:form.RestoreBounds;
            if(bounds.Width<=0||bounds.Height<=0)return;
            try
            {
                var saved=new Placement(bounds.X,bounds.Y,bounds.Width,bounds.Height,form.WindowState==FormWindowState.Maximized);
                File.WriteAllText(path+".tmp",JsonSerializer.Serialize(saved));
                File.Move(path+".tmp",path,true);
            }
            catch(Exception ex){AppDebugLog.Write("window","placement_save_failed",ex);}
        }
        timer.Tick+=(_,_)=>{timer.Stop();Save();};
        void Schedule(){if(!shown)return;timer.Stop();timer.Start();}
        form.Shown+=(_,_)=>{shown=true;Save();};
        form.LocationChanged+=(_,_)=>Schedule();
        form.SizeChanged+=(_,_)=>Schedule();
        form.FormClosing+=(_,_)=>Save();
        form.FormClosed+=(_,_)=>timer.Dispose();
    }
}
