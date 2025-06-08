import maya.cmds as cmds
import maya.api.OpenMaya as om
import os
import json

class SkinWeightToolUI:
    def __init__(self):
        self.window = "WeightExportToolUI"
        self.widgets = {}

        # プロジェクトの scenes/_weight フォルダを取得して保存先にする
        scenes_path = cmds.workspace(q=True, rootDirectory=True) + "scenes"
        self.folder_path = os.path.join(scenes_path, "_weight")
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)

    def show(self):
        if cmds.window(self.window, exists=True):
            cmds.deleteUI(self.window)

        self.window = cmds.window(self.window, title="ウェイトエクスポートツール", widthHeight=(400, 500))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=10)
        tabs = cmds.tabLayout(innerMarginWidth=5, innerMarginHeight=5)

        # ---------- タブ1: エクスポート/インポート ----------
        tab1 = cmds.columnLayout(adjustableColumn=True, rowSpacing=10)        

        cmds.text(label="IMPORT")
        self.widgets["fileList"] = cmds.textScrollList(numberOfRows=8, allowMultiSelection=False, height=150)

        cmds.text(label="インポート方法")
        self.widgets["mode"] = cmds.radioButtonGrp(labelArray3=["頂点番号", "頂点位置", "UV座標値"],
                                                   numberOfRadioButtons=3, select=1)

        cmds.button(label="インポートする", command=self.import_clicked)

        cmds.separator(style="in")
        cmds.text(label="サフィックスをつける")
        self.widgets["suffix"] = cmds.textField()

        cmds.button(label="エクスポートする", command=self.export_clicked)

        cmds.separator(style="in")
        cmds.text(label=f"保存先: {self.folder_path}")

        cmds.button(label="ファイル一覧を更新", command=self.refresh_file_list)
        cmds.setParent("..")  #たぶ1

        # ---------- タブ2: 補間ツールなど ----------
        tab2 = cmds.columnLayout(adjustableColumn=True, rowSpacing=10)
        cmds.separator(h=10)
        cmds.button(label="選択した項目順にグラデーション補完", command=self.interpolate_weights_along_vertices)
        cmds.setParent("..")

        cmds.tabLayout(tabs, edit=True, tabLabel=[
            (tab1, "ウェイト I/O"),
            (tab2, "補間ツール（仮）")
        ])

        cmds.showWindow(self.window)

    def get_skin_cluster(self, mesh_name):
        history = cmds.listHistory(mesh_name)
        skin_clusters = cmds.ls(history, type='skinCluster')
        return skin_clusters[0] if skin_clusters else None

    def export_weights(self, mesh, file_path):
        skin_cluster = self.get_skin_cluster(mesh)
        if not skin_cluster:
            cmds.warning(f"{mesh} にスキンクラスタが見つかりません。")
            return

        influences = cmds.skinCluster(skin_cluster, q=True, inf=True)
        weights, positions, uvs = [], [], []

        for i in range(cmds.polyEvaluate(mesh, vertex=True)):
            w = cmds.skinPercent(skin_cluster, f"{mesh}.vtx[{i}]", q=True, v=True)
            weights.append(w)
            positions.append(cmds.pointPosition(f"{mesh}.vtx[{i}]", w=True))
            uv = cmds.polyEditUV(cmds.polyListComponentConversion(f"{mesh}.vtx[{i}]", fv=True, tuv=True)[0], q=True)
            uvs.append(uv if uv else [0.0, 0.0])

        data = {
            "mesh": mesh,
            "influences": influences,
            "weights": weights,
            "positions": positions,
            "uvs": uvs
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def import_weights(self, mesh, file_path, mode):
        if not os.path.exists(file_path):
            cmds.warning(f"ファイルが見つかりません: {file_path}")
            return

        with open(file_path, "r") as f:
            data = json.load(f)

        influences = data["influences"]
        weights = data["weights"]
        positions = data["positions"]
        uvs = data["uvs"]

        skin_cluster = self.get_skin_cluster(mesh)
        if not skin_cluster:
            skin_cluster = cmds.skinCluster(influences, mesh, toSelectedBones=True)[0]

        count = cmds.polyEvaluate(mesh, vertex=True)
        for i in range(count):
            if mode == "index":
                if i >= len(weights): continue
                w = weights[i]
            elif mode == "position":
                p = cmds.pointPosition(f"{mesh}.vtx[{i}]", w=True)
                idx = min(range(len(positions)), key=lambda j: sum([(p[k]-positions[j][k])**2 for k in range(3)]))
                w = weights[idx]
            elif mode == "uv":
                uv = cmds.polyEditUV(cmds.polyListComponentConversion(f"{mesh}.vtx[{i}]", fv=True, tuv=True)[0], q=True)
                idx = min(range(len(uvs)), key=lambda j: sum([(uv[k]-uvs[j][k])**2 for k in range(2)]))
                w = weights[idx]
            else:
                continue

            cmds.skinPercent(skin_cluster, f"{mesh}.vtx[{i}]", transformValue=list(zip(influences, w)))

    def refresh_file_list(self, *_):
        files = [f for f in os.listdir(self.folder_path) if f.endswith(".json")]
        cmds.textScrollList(self.widgets["fileList"], e=True, removeAll=True)
        for f in files:
            cmds.textScrollList(self.widgets["fileList"], e=True, append=f)

    def export_clicked(self, *_):
        suffix = cmds.textField(self.widgets["suffix"], q=True, text=True)
        selection = cmds.ls(sl=True, type="transform")
        if not selection:
            cmds.warning("メッシュを選択してください")
            return

        for mesh in selection:
            filename = f"{mesh}_{suffix}.json" if suffix else f"{mesh}.json"
            path = os.path.join(self.folder_path, filename)
            self.export_weights(mesh, path)

        cmds.inViewMessage(amg="エクスポート完了", pos="topCenter", fade=True)
        self.refresh_file_list()

    def import_clicked(self, *_):
        selected = cmds.textScrollList(self.widgets["fileList"], q=True, selectItem=True)
        if not selected:
            cmds.warning("ファイルを選択してください")
            return

        mode_id = cmds.radioButtonGrp(self.widgets["mode"], q=True, select=True)
        mode_str = {1: "index", 2: "position", 3: "uv"}[mode_id]

        file_path = os.path.join(self.folder_path, selected[0])
        selection = cmds.ls(sl=True, type="transform")
        if not selection:
            cmds.warning("インポート先メッシュを選択してください")
            return

        for mesh in selection:
            self.import_weights(mesh, file_path, mode_str)

        cmds.inViewMessage(amg="インポート完了", pos="topCenter", fade=True)

    def interpolate_weights_along_vertices(self, *_):
        #使用の場合は選択した順番に頂点を取得するため、プリファレンス→選択項目→選択順をトラック＆アウトライナの選択～～をONにしてください
        sel = cmds.ls(os=True, fl=True)
        if len(sel) < 3:
            cmds.warning("3つ以上の頂点を順序付きで選択してください。")
            return

        start_vtx = sel[0]
        end_vtx = sel[-1]
        mesh = start_vtx.split(".vtx")[0]

        # スキンクラスタ取得
        skin_cluster = None
        for node in cmds.listHistory(mesh):
            if cmds.nodeType(node) == "skinCluster":
                skin_cluster = node
                break

        if not skin_cluster:
            cmds.warning(f"{mesh} にスキンクラスタが見つかりません。")
            return

        # インフルエンス取得
        influences = cmds.skinCluster(skin_cluster, q=True, inf=True)
        w_start = cmds.skinPercent(skin_cluster, start_vtx, q=True, v=True)
        w_end = cmds.skinPercent(skin_cluster, end_vtx, q=True, v=True)

        # グラデーション補間を各頂点に適用
        total = len(sel) - 1  # 0〜NのN部分
        for idx, vtx in enumerate(sel):
            t = idx / total  # 0.0 ～ 1.0 の割合
            w_interp = [(1 - t) * a + t * b for a, b in zip(w_start, w_end)]
            weight_pairs = list(zip(influences, w_interp))
            cmds.skinPercent(skin_cluster, vtx, transformValue=weight_pairs)

        cmds.inViewMessage(amg="選択頂点にウェイトをグラデーション適用しました", pos="topCenter", fade=True)


# 実行
tool = SkinWeightToolUI()
tool.show()
