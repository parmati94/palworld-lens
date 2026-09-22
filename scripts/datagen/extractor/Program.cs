using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Versions;
using CUE4Parse.Compression;
using CUE4Parse_Conversion.Textures;
using CUE4Parse.UE4.Assets.Exports.Engine;
using Newtonsoft.Json;

namespace PalworldLens.Extractor;

// Minimal Palworld icon extractor (PoC). Palworld is UE5.1; its dedicated-server pak
// (Pal-LinuxServer.pak) is unencrypted, so a zero AES key works. A usmap is only
// needed for property-level parsing (LoadPackage / texture decode), NOT for mounting
// or raw byte extraction.
internal static class Program
{
    // Dir containing the .pak(s) to mount. Point at the Palworld server's Paks dir,
    // or a mirror under ~/.gamedata/palworld-pak-data/input.
    private static string InputDir =>
        Environment.GetEnvironmentVariable("PALWORLD_PAK_DIR")
        ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                        ".gamedata", "palworld-pak-data", "input");

    // Optional mappings file (community-dumped Palworld.usmap). If present, enables
    // property parsing / texture decode; if absent, only smoke/pull work.
    private static string? Usmap =>
        Environment.GetEnvironmentVariable("PALWORLD_USMAP") is { Length: > 0 } p && File.Exists(p) ? p : null;

    private static string OodlePath =>
        Path.Combine(AppContext.BaseDirectory, "runtime", "liboodle-data-shared.so");

    private static readonly EGame Game = EGame.GAME_UE5_1;

    private static int Main(string[] args)
    {
        var cmd = args.Length > 0 ? args[0] : "smoke";
        var provider = Setup();
        Console.WriteLine($"mounted {provider.Files.Count} files; usmap={(Usmap ?? "<none>")}; command='{cmd}'");

        switch (cmd)
        {
            case "smoke": return Smoke(provider, args.Length > 1 ? args[1] : "Alpaca_icon");
            case "pull":  return Pull(provider, args[1], args[2]);
            case "tex":   return Tex(provider, args[1], args[2]);
            case "icons": return Icons(provider, args[1], args[2]);
            case "dt":    return Dt(provider, args[1], args.Length > 2 ? args[2] : null);
            case "list":  return List(provider, args.Length > 1 ? args[1] : "", args.Length > 2 ? args[2] : null);
            default:
                Console.Error.WriteLine($"unknown command: {cmd}");
                return 2;
        }
    }

    private static DefaultFileProvider Setup()
    {
        OodleHelper.Initialize(OodlePath);
        var provider = new DefaultFileProvider(
            InputDir, SearchOption.AllDirectories, isCaseInsensitive: true, new VersionContainer(Game));
        if (Usmap != null)
            provider.MappingsContainer = new FileUsmapTypeMappingsProvider(Usmap);
        provider.Initialize();
        provider.SubmitKey(new FGuid(), new FAesKey(new byte[32]));   // unencrypted → zero key
        return provider;
    }

    // Mount + list keys matching a substring. Proves the pak reads as UE5.1.
    private static int Smoke(DefaultFileProvider provider, string needle)
    {
        var hits = provider.Files.Keys
            .Where(k => k.Contains(needle, StringComparison.OrdinalIgnoreCase))
            .OrderBy(k => k).Take(25).ToList();
        Console.WriteLine($"keys containing '{needle}': {hits.Count} (showing up to 25)");
        foreach (var k in hits) Console.WriteLine($"  {k}");
        return hits.Count > 0 ? 0 : 1;
    }

    // Raw-copy every key whose filename contains <needle> (all extensions) to <outDir>.
    // No property parsing → no usmap required.
    private static int Pull(DefaultFileProvider provider, string needle, string outDir)
    {
        var keys = provider.Files.Keys
            .Where(k => Path.GetFileName(k).Contains(needle, StringComparison.OrdinalIgnoreCase))
            .ToList();
        Console.WriteLine($"pull: {keys.Count} files matching '{needle}' → {outDir}");
        int ok = 0;
        foreach (var key in keys)
        {
            try
            {
                var bytes = provider.SaveAsset(key);
                var outPath = Path.Combine(outDir, key.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
                File.WriteAllBytes(outPath, bytes);
                Console.WriteLine($"  OK {key} ({bytes.Length} bytes)");
                ok++;
            }
            catch (Exception ex) { Console.Error.WriteLine($"  FAIL {key}: {ex.Message}"); }
        }
        return ok > 0 ? 0 : 1;
    }

    // Batch: decode every icon named in <listFile> (one texture basename per line, e.g.
    // "t_alpaca_icon_normal") to <outDir>/<name>.rgba + .json. Names are matched to pak
    // keys case-insensitively by filename. Output names are lowercased to match our
    // frontend/public/img convention. Requires a usmap (unversioned client props).
    private static int Icons(DefaultFileProvider provider, string listFile, string outDir)
    {
        // basename(no ext, lowercased) → mount key, for all texture packages.
        var byName = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var k in provider.Files.Keys)
        {
            if (!k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase)) continue;
            byName.TryAdd(Path.GetFileNameWithoutExtension(k), k);
        }
        var wanted = File.ReadAllLines(listFile).Select(l => l.Trim())
            .Where(l => l.Length > 0).Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        Console.WriteLine($"icons: {wanted.Count} requested; {byName.Count} textures in pak → {outDir}");
        Directory.CreateDirectory(outDir);

        int ok = 0, missing = 0, fail = 0;
        Parallel.ForEach(wanted, ParallelOpts, name =>
        {
            if (!byName.TryGetValue(name, out var key))
            {
                if (Interlocked.Increment(ref missing) <= 20) Console.Error.WriteLine($"  NOT-IN-PAK {name}");
                return;
            }
            try
            {
                var pkg = provider.LoadPackage(key);
                var tex = pkg.GetExports().OfType<UTexture2D>().FirstOrDefault();
                if (tex == null) { if (Interlocked.Increment(ref fail) <= 20) Console.Error.WriteLine($"  NO-TEX {name}"); return; }
                var ctex = tex.Decode();
                if (ctex == null) { if (Interlocked.Increment(ref fail) <= 20) Console.Error.WriteLine($"  DECODE-NULL {name}"); return; }
                var stem = Path.Combine(outDir, name.ToLowerInvariant());
                File.WriteAllBytes(stem + ".rgba", ctex.Data);
                File.WriteAllText(stem + ".json",
                    $"{{\"width\":{ctex.Width},\"height\":{ctex.Height},\"pixelFormat\":\"{ctex.PixelFormat}\"}}");
                var n = Interlocked.Increment(ref ok);
                if (n % 200 == 0) Console.WriteLine($"  ...{n}");
            }
            catch (Exception ex) { if (Interlocked.Increment(ref fail) <= 20) Console.Error.WriteLine($"  FAIL {name}: {ex.Message}"); }
        });
        Console.WriteLine($"done: {ok} decoded, {missing} not in pak, {fail} failed");
        return 0;
    }

    private static ParallelOptions ParallelOpts => new() { MaxDegreeOfParallelism = Environment.ProcessorCount };

    // Dump all mount keys containing <needle> (or all) to <outFile> or stdout.
    private static int List(DefaultFileProvider provider, string needle, string? outFile)
    {
        var keys = provider.Files.Keys
            .Where(k => needle.Length == 0 || k.Contains(needle, StringComparison.OrdinalIgnoreCase))
            .OrderBy(k => k, StringComparer.OrdinalIgnoreCase).ToList();
        if (outFile != null) { File.WriteAllLines(outFile, keys); Console.WriteLine($"wrote {keys.Count} keys → {outFile}"); }
        else foreach (var k in keys) Console.WriteLine(k);
        return 0;
    }

    // Export a UDataTable as JSON. Palworld's game data lives in DataTables and most
    // of them read cleanly -- DT_ItemDataTable (2466 rows), DT_PassiveSkill_Main (1905),
    // DT_BuildObjectDataTable (498), the per-language *NameText tables, and
    // DT_WorldMapUIData, which is where the map layers' world bounds come from.
    //
    // NOTE DT_PalMonsterParameter (pal stats) ships with ZERO rows in the client pak --
    // it declares its RowStruct and nothing else -- which is why data/json still comes
    // from palworld-save-pal rather than being generated here.
    private static int Dt(DefaultFileProvider provider, string needle, string? outFile)
    {
        // Bare name (first match, any language) or a pak path such as
        // Pal/Content/L10N/en/Pal/DataTable/Text/DT_SkillNameText_Common to pin one.
        var key = provider.Files.Keys.FirstOrDefault(k =>
            k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase) &&
            (needle.Contains('/')
                ? k.Equals(needle + ".uasset", StringComparison.OrdinalIgnoreCase) || k.Equals(needle, StringComparison.OrdinalIgnoreCase)
                : Path.GetFileNameWithoutExtension(k).Equals(needle, StringComparison.OrdinalIgnoreCase)));
        if (key == null) { Console.Error.WriteLine($"no .uasset named '{needle}'"); return 1; }
        Console.WriteLine($"dt: {key}");
        try
        {
            var pkg = provider.LoadPackage(key);
            var table = pkg.GetExports().OfType<UDataTable>().FirstOrDefault();
            if (table == null)
            {
                Console.Error.WriteLine($"  not a UDataTable; exports: " +
                    string.Join(", ", pkg.GetExports().Select(e => e.ExportType)));
                return 1;
            }
            Console.WriteLine($"  rows: {table.RowMap.Count}");
            var first = table.RowMap.FirstOrDefault();
            Console.WriteLine($"  first row key: {first.Key}");
            if (first.Value != null)
                Console.WriteLine($"  columns ({first.Value.Properties.Count}): " +
                    string.Join(", ", first.Value.Properties.Take(12).Select(x => x.Name.Text)));
            var json = JsonConvert.SerializeObject(table, Formatting.Indented);
            if (outFile != null) { File.WriteAllText(outFile, json); Console.WriteLine($"  wrote {json.Length} chars -> {outFile}"); }
            return 0;
        }
        catch (Exception ex) { Console.Error.WriteLine($"  FAILED: {ex.GetType().Name}: {ex.Message}"); return 1; }
    }

    // Full CUE4Parse decode: load the first texture matching <needle> and write PNG.
    // Tests whether we need a usmap and whether SkiaSharp decode works on this host.
    private static int Tex(DefaultFileProvider provider, string needle, string outDir)
    {
        var key = provider.Files.Keys.FirstOrDefault(k =>
            k.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase) &&
            Path.GetFileName(k).Contains(needle, StringComparison.OrdinalIgnoreCase));
        if (key == null) { Console.Error.WriteLine($"no .uasset matching '{needle}'"); return 1; }
        Console.WriteLine($"tex: {key}");
        try
        {
            var pkg = provider.LoadPackage(key);
            var exports = pkg.GetExports().ToList();
            Console.WriteLine($"  exports: {string.Join(", ", exports.Select(e => e.ExportType))}");
            var tex = exports.OfType<UTexture2D>().FirstOrDefault();
            if (tex == null) { Console.Error.WriteLine("  no UTexture2D export"); return 1; }
            Console.WriteLine($"  tagged properties: {(tex.Properties.Count == 0 ? "<none>" : string.Join(", ", tex.Properties.Select(p => p.Name.Text)))}");
            var pd = tex.PlatformData;
            Console.WriteLine($"  format={tex.Format} platformData={(pd == null ? "null" : "ok")} " +
                              $"mips={pd?.Mips?.Length ?? -1} firstMipBytes={tex.GetFirstMip()?.BulkData?.Data?.Length ?? -1}");
            var ctex = tex.Decode();
            if (ctex == null) { Console.Error.WriteLine("  Decode() returned null"); return 1; }
            Console.WriteLine($"  decoded {ctex.Width}x{ctex.Height} pf={ctex.PixelFormat} dataLen={ctex.Data.Length}");
            // Write raw decoded pixels (CTexture.Data) + a sidecar; PIL encodes the final
            // image (avoids SkiaSharp's native lib, and we need PIL for webp anyway).
            Directory.CreateDirectory(outDir);
            var stem = Path.Combine(outDir, Path.GetFileNameWithoutExtension(key));
            File.WriteAllBytes(stem + ".rgba", ctex.Data);
            File.WriteAllText(stem + ".json",
                $"{{\"width\":{ctex.Width},\"height\":{ctex.Height},\"pixelFormat\":\"{ctex.PixelFormat}\"}}");
            Console.WriteLine($"  wrote {stem}.rgba ({ctex.Data.Length} bytes)");
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"  DECODE FAILED: {ex.GetType().Name}: {ex.Message}");
            return 1;
        }
    }
}
