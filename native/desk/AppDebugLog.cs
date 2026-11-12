using System.Text.Json;

internal static class AppDebugLog
{
    internal static string? DirectoryOverride;
    static readonly object Gate=new();
    static readonly Dictionary<string,DateTime> Recent=new();
    internal static void Write(string component,string code,Exception? error=null,object? details=null)
    {
        try {
            lock(Gate){
                var now=DateTime.UtcNow;var signature=component+code+error?.GetType().Name;
                if(error!=null&&Recent.TryGetValue(signature,out var last)&&(now-last).TotalSeconds<60)return;
                Recent[signature]=now;
                var folder=DirectoryOverride??Path.GetFullPath(Path.Combine(AppContext.BaseDirectory,"../debug"));Directory.CreateDirectory(folder);
                var file=Path.Combine(folder,"desk-debug.jsonl");
                if(File.Exists(file)&&new FileInfo(file).Length>2_000_000)File.Move(file,Path.Combine(folder,"desk-debug-"+now.ToString("yyyyMMddTHHmmssfff")+".jsonl"));
                // Never log memo text, clipboard data, response bodies, URLs with queries or exception messages.
                var record=new{at=now.ToString("O"),pid=Environment.ProcessId,component,code,errorType=error?.GetType().Name,hresult=error?.HResult,details};
                File.AppendAllText(file,JsonSerializer.Serialize(record)+Environment.NewLine);
            }
        }catch{ /* logging must not destroy a writing session */ }
    }
}
