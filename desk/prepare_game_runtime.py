"""Prepare a disposable native world; never change the canonical game."""
from pathlib import Path
import shutil,json,hashlib,subprocess

ROOT=Path(__file__).resolve().parent
import os
ENGINE=Path(os.environ.get('LUANTI_ENGINE_ROOT', 'configure-your-luanti-engine'))
RUNTIME=ROOT/'game-runtime'
WORLD=RUNTIME/'story-world'

def prepare():
    source=ENGINE/'games/oasis_game'
    WORLD.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source,WORLD/'game',dirs_exist_ok=True)
    shutil.copytree(ROOT/'game-candidate/lava_fortress_demo',WORLD/'game/mods/lava_fortress_demo',dirs_exist_ok=True)
    (WORLD/'world.mt').write_text('gameid = oasis_game\nbackend = sqlite3\nplayer_backend = sqlite3\nauth_backend = sqlite3\nmod_storage_backend = sqlite3\ncreative_mode = true\nenable_damage = false\n',encoding='utf-8')
    config='mg_name = flat\nmg_flags = nocaves,nodungeons,nolight,decorations,biomes\nfixed_map_seed = 172941\nenable_damage = false\ncreative_mode = true\nenable_sound = false\nserver_announce = false\nserver_address = 127.0.0.1\nbind_address = 127.0.0.1\nport = 30167\nlava_fortress_intro_autostart = true\n'
    (RUNTIME/'story.conf').write_text(config,encoding='utf-8')
    launch="""$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$engine='ENGINE_EXE'
if(-not(Test-Path -LiteralPath $engine)){throw 'Native Luanti executable is missing.'}
Start-Process -FilePath $engine -ArgumentList @('--go','--world',('"'+(Join-Path $root 'story-world')+'"'),'--config',('"'+(Join-Path $root 'story.conf')+'"'),'--name','GameDeskPlayer','--logfile',('"'+(Join-Path $root 'player.log')+'"')) -WorkingDirectory $root
""".replace('ENGINE_EXE',str(ENGINE/'bin/luanti.exe'))
    (RUNTIME/'Play-Story.ps1').write_text(launch,encoding='utf-8-sig')
    return {'world':str(WORLD),'nativeEngine':str(ENGINE/'bin/luanti.exe'),'canonicalSourceChanged':False,'seed':172941,'entry':'Play-Story.ps1; auto intro or /lava_fortress'}

def headless_check():
    # A separate copy avoids leaving a shutdown-only QA mod in the playable world.
    qa=RUNTIME/'headless-check-world'
    shutil.copytree(WORLD,qa,dirs_exist_ok=True)
    checks=qa/'game/mods/desk_load_check';checks.mkdir(exist_ok=True)
    (checks/'mod.conf').write_text('name = desk_load_check\ndepends = lava_fortress_demo\n',encoding='utf-8')
    (checks/'init.lua').write_text('''minetest.register_on_mods_loaded(function()
  assert(minetest.registered_chatcommands.lava_fortress, "Missing battle entry")
  local p = minetest.get_modpath("lava_fortress_demo")
  assert(io.open(p .. "/prologue.lua", "r"), "Missing prologue module")
  for i=1,4 do
    local f=assert(io.open(p .. "/textures/lava_prologue_0" .. i .. ".png", "rb"))
    assert(f:read(8)=="\\137PNG\\13\\10\\26\\10", "Invalid story card"); f:close()
  end
  minetest.log("action", "[DESK_NATIVE_LOAD_OK] module + entry + 4 PNG cards loaded")
  minetest.after(1,function() minetest.request_shutdown("desk bounded load check complete", false, 0) end)
end)
''',encoding='utf-8')
    log=RUNTIME/'native-load.log'
    result=subprocess.run([str(ENGINE/'bin/luanti.exe'),'--server','--world',str(qa),'--config',str(RUNTIME/'story.conf'),'--port','30168','--logfile',str(log)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    content=log.read_text(encoding='utf-8',errors='replace') if log.exists() else ''
    receipt={'kind':'native-headless-mod-load','exitCode':result.returncode,'loaded':result.returncode==0 and '[DESK_NATIVE_LOAD_OK]' in content,'log':str(log),'realGameplay':False,'renderingVerified':False,'inputVerified':False,'canonicalSourceChanged':False}
    (RUNTIME/'NATIVE-LOAD-CHECK.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt));print((result.stderr+result.stdout)[-1800:])
    return receipt

if __name__=='__main__':
    print(json.dumps(prepare())); headless_check()
